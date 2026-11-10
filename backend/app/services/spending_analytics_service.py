"""Provisional read-only analytics and anomaly logic for Developer 1 to integrate."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext
from typing import TYPE_CHECKING, Protocol
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import TypeAdapter
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..schemas import _Currency
from ..spending_analytics_schemas import (
    AnomalyCandidate,
    AnomalyPolicy,
    AnomalyResult,
    CategorySpending,
    MonthlySpendingSummary,
    MonthlySpendingTrend,
)

if TYPE_CHECKING:
    from ..models import Expense

_CURRENCY = TypeAdapter(_Currency)
_ZERO = Decimal("0")
_BASIS_POINTS = Decimal("10000")
_PERCENT_UNIT = Decimal("0.01")


class AnalyticsInputError(ValueError):
    """An invalid reporting period or anomaly candidate."""


@dataclass(frozen=True)
class SpendingRecord:
    id: UUID
    user_id: UUID
    transaction_date: date
    created_at: datetime
    category: str | None
    currency: str
    amount: Decimal


class SpendingRepository(Protocol):
    def expenses(
        self,
        user_id: UUID,
        currency: str,
        *,
        start: date | None,
        end: date | None,
        category: str | None,
    ) -> Iterable[SpendingRecord]: ...


class SQLAlchemySpendingRepository:
    """Select only analytics fields using the shared session and Expense mapping."""

    def __init__(self, session: Session, expense_model: type[Expense]) -> None:
        self._session = session
        self._expense = expense_model

    def expenses(
        self,
        user_id: UUID,
        currency: str,
        *,
        start: date | None,
        end: date | None,
        category: str | None,
    ) -> Iterator[SpendingRecord]:
        expense = self._expense
        statement = select(
            expense.id, expense.user_id, expense.transaction_date, expense.created_at,
            expense.category, expense.currency, expense.amount,
        ).where(expense.user_id == user_id, expense.currency == currency)
        if start is not None:
            statement = statement.where(expense.transaction_date >= start)
        if end is not None:
            statement = statement.where(expense.transaction_date < end)
        if category is not None:
            statement = statement.where(expense.category == category)
        for row in self._session.execute(statement).mappings():
            yield SpendingRecord(**row)


class SpendingAnalyticsService:
    def __init__(
        self, repository: SpendingRepository, user_id: UUID, *, currency: str = "PKR"
    ) -> None:
        if not isinstance(user_id, UUID):
            raise TypeError("Spending analytics requires an authenticated user's UUID")
        self._repository = repository
        self._user_id = user_id
        self._currency = _CURRENCY.validate_python(currency)
        self._timezone = ZoneInfo("Asia/Karachi")

    @property
    def user_id(self) -> UUID:
        return self._user_id

    def monthly(
        self, year: int, month: int, *, reference_datetime: datetime | None = None
    ) -> MonthlySpendingSummary:
        as_of = self._local_reference(reference_datetime).date()
        start = date(year, month, 1)
        through = _report_through(start, as_of)
        rows = self._scoped_records(start=start, end=_next_day(through))
        return _summarize(start, through, as_of, self._currency, rows)

    def trends(
        self,
        months: int = 3,
        *,
        end_month: date | None = None,
        reference_datetime: datetime | None = None,
    ) -> list[MonthlySpendingTrend]:
        if type(months) is not int or not 1 <= months <= 120:
            raise AnalyticsInputError("months must be an integer between 1 and 120")
        as_of = self._local_reference(reference_datetime).date()
        final_month = (end_month or as_of).replace(day=1)
        through = _report_through(final_month, as_of)
        index = (final_month.year - 1) * 12 + final_month.month - 1
        if index + 1 < months:
            raise AnalyticsInputError("Trend window precedes the supported calendar")
        starts = [date(i // 12 + 1, i % 12 + 1, 1) for i in range(index - months + 1, index + 1)]

        by_month: dict[date, list[SpendingRecord]] = defaultdict(list)
        for row in self._scoped_records(start=starts[0], end=_next_day(through)):
            by_month[row.transaction_date.replace(day=1)].append(row)

        points = []
        previous = None
        for start in starts:
            summary = _summarize(start, _report_through(start, as_of), as_of, self._currency, by_month[start])
            change, percentage = _change(summary.total_spent, previous)
            points.append(MonthlySpendingTrend(
                **summary.model_dump(), change_amount=change, change_percentage=percentage,
            ))
            previous = summary.total_spent
        return points

    def check_anomaly(
        self,
        candidate: AnomalyCandidate,
        *,
        policy: AnomalyPolicy = AnomalyPolicy(),
        saved: SpendingRecord | None = None,
        reference_datetime: datetime | None = None,
    ) -> AnomalyResult:
        reference = self._local_reference(reference_datetime)
        if candidate.currency != self._currency:
            raise AnalyticsInputError("Candidate currency must match the analytics currency")
        if candidate.transaction_date > reference.date():
            raise AnalyticsInputError("Candidate transaction_date cannot be in the future")
        if saved is not None and (
            saved.user_id != self._user_id
            or saved.currency != candidate.currency
            or saved.category != candidate.category
            or saved.transaction_date != candidate.transaction_date
            or saved.amount != candidate.amount
            or saved.created_at.utcoffset() is None
            or saved.created_at > reference
        ):
            raise AnalyticsInputError("Saved expense must match the authenticated candidate")

        # A backdated draft has no trustworthy position within its transaction day.
        include_same_day = saved is not None or candidate.transaction_date == reference.date()
        end = _next_day(candidate.transaction_date) if include_same_day else candidate.transaction_date
        rows = self._scoped_records(end=end, category=candidate.category)
        cutoff = saved.created_at if saved is not None else reference
        amounts = [
            row.amount for row in rows
            if row.created_at.utcoffset() is not None and row.created_at <= cutoff
            and (saved is None or (row.id != saved.id and _order(row) < _order(saved)))
        ]
        return _anomaly_result(candidate, policy, amounts, saved.id if saved is not None else None)

    def latest_anomaly(
        self, summary: MonthlySpendingSummary, *, reference_datetime: datetime
    ) -> AnomalyResult | None:
        reference = self._local_reference(reference_datetime)
        start = date(summary.year, summary.month, 1)
        rows = self._scoped_records(start=start, end=_next_day(summary.through_date))
        eligible = (
            row for row in rows if row.category and row.category.strip() and row.amount > 0
            and row.created_at.utcoffset() is not None and row.created_at <= reference
        )
        latest = max(eligible, key=_order, default=None)
        if latest is None:
            return None
        candidate = AnomalyCandidate(
            amount=latest.amount, category=latest.category,
            transaction_date=latest.transaction_date, currency=latest.currency,
        )
        return self.check_anomaly(candidate, saved=latest, reference_datetime=reference)

    def _scoped_records(
        self, *, start: date | None = None, end: date | None = None, category: str | None = None
    ) -> Iterable[SpendingRecord]:
        rows: dict[UUID, SpendingRecord] = {}
        conflicts = set()
        for row in self._repository.expenses(
            self._user_id, self._currency, start=start, end=end, category=category,
        ):
            if (
                row.user_id != self._user_id or row.currency != self._currency
                or (start is not None and row.transaction_date < start)
                or (end is not None and row.transaction_date >= end)
                or (category is not None and row.category != category)
                or not isinstance(row.amount, Decimal) or not row.amount.is_finite() or row.amount < 0
            ):
                continue
            if row.id in rows and rows[row.id] != row:
                conflicts.add(row.id)
            else:
                rows[row.id] = row
        return (row for key, row in rows.items() if key not in conflicts)

    def _local_reference(self, reference_datetime: datetime | None) -> datetime:
        reference = reference_datetime or datetime.now(timezone.utc)
        if reference.utcoffset() is None:
            raise ValueError("reference_datetime must be timezone-aware")
        return reference.astimezone(self._timezone)


def _next_day(value: date) -> date | None:
    return value + timedelta(days=1) if value < date.max else None


def _report_through(start: date, as_of: date) -> date:
    if start > as_of:
        raise AnalyticsInputError("Spending periods cannot start in the future")
    if start.year == as_of.year and start.month == as_of.month:
        return as_of
    next_month = date(start.year + (start.month == 12), start.month % 12 + 1, 1)
    return next_month - timedelta(days=1)


def _order(row: SpendingRecord) -> tuple[date, datetime, UUID]:
    return row.transaction_date, row.created_at, row.id


@contextmanager
def _finance_context(values: Sequence[Decimal]) -> Iterator[None]:
    # Include enough significant digits for exact sums and products before rounding quotients.
    highest = max((value.adjusted() for value in values), default=0)
    lowest = min((value.as_tuple().exponent for value in values), default=0)
    span = max(highest, 0) - min(lowest, 0) + 1
    precision = max(34, 2 * span + len(str(len(values))) + 12)
    with localcontext(Context(prec=precision, rounding=ROUND_HALF_EVEN)):
        yield


def _summarize(
    start: date, through: date, as_of: date, currency: str, rows: Iterable[SpendingRecord]
) -> MonthlySpendingSummary:
    groups: dict[str | None, list[Decimal]] = defaultdict(list)
    for row in rows:
        groups[row.category if row.category and row.category.strip() else None].append(row.amount)
    amounts = [amount for group in groups.values() for amount in group]
    with _finance_context(amounts):
        total = sum(amounts, _ZERO)
        counts = {category: (sum(values, _ZERO), len(values)) for category, values in groups.items()}
        breakdown = _category_breakdown(counts, total)
        average = total / len(amounts) if amounts else None
    return MonthlySpendingSummary(
        year=start.year, month=start.month, currency=currency, total_spent=total,
        transaction_count=len(amounts), average_expense=average, categories=breakdown,
        is_partial=start == as_of.replace(day=1), through_date=through,
    )


def _category_breakdown(
    groups: dict[str | None, tuple[Decimal, int]], total: Decimal,
) -> list[CategorySpending]:
    # Assign the remaining hundredths of a percent by largest remainder, with stable ties.
    ordered = sorted(groups, key=lambda name: (name is None, name or ""))
    shares = [divmod(groups[name][0] * _BASIS_POINTS, total) for name in ordered] if total else []
    points = [share[0] for share in shares] if total else [_ZERO] * len(ordered)
    if total:
        remainder_order = sorted(range(len(shares)), key=lambda i: shares[i][1], reverse=True)
        for index in remainder_order[:int(_BASIS_POINTS - sum(points, _ZERO))]:
            points[index] += 1
    return [
        CategorySpending(
            category=name, total_spent=groups[name][0], transaction_count=groups[name][1],
            percentage_of_total=points[index] * _PERCENT_UNIT,
        )
        for index, name in enumerate(ordered)
    ]


def _change(current: Decimal, previous: Decimal | None) -> tuple[Decimal | None, Decimal | None]:
    if previous is None:
        return None, None
    with _finance_context([current, previous]):
        change = current - previous
        percentage = (change * 100 / previous).quantize(_PERCENT_UNIT) if previous else None
        return change, percentage


def _anomaly_result(
    candidate: AnomalyCandidate, policy: AnomalyPolicy, amounts: list[Decimal], expense_id: UUID | None,
) -> AnomalyResult:
    count = len(amounts)
    baseline = threshold = None
    unusual = False
    if count < policy.minimum_history:
        status = "insufficient_history"
        explanation = f"Only {count} previous {candidate.category} expenses. {policy.minimum_history} required."
    else:
        with _finance_context([*amounts, candidate.amount, policy.threshold_multiplier]):
            if policy.baseline_method == "mean":
                total = sum(amounts, _ZERO)
                baseline = total / count
                exceeds = candidate.amount * count > total * policy.threshold_multiplier
            else:
                amounts.sort()
                lower, upper = amounts[(count - 1) // 2], amounts[count // 2]
                baseline = (lower + upper) / 2
                exceeds = candidate.amount > baseline * policy.threshold_multiplier
            threshold = baseline * policy.threshold_multiplier
        if not baseline:
            status = "unavailable_baseline"
            explanation = f"Previous {candidate.category} expenses have a zero spending baseline."
        else:
            unusual = exceeds and candidate.amount > policy.minimum_amount
            status = "unusual" if unusual else "normal"
            comparison = "exceeds" if unusual else "does not exceed both"
            explanation = f"Transaction {comparison} the configured thresholds based on {count} previous {candidate.category} expenses."
    return AnomalyResult(
        expense_id=expense_id, status=status, is_unusual=unusual,
        has_enough_history=count >= policy.minimum_history, category=candidate.category,
        currency=candidate.currency, amount=candidate.amount, sample_count=count,
        minimum_history=policy.minimum_history, baseline_method=policy.baseline_method,
        baseline_amount=baseline, threshold_amount=threshold,
        threshold_multiplier=policy.threshold_multiplier, minimum_amount=policy.minimum_amount,
        explanation=explanation,
    )
