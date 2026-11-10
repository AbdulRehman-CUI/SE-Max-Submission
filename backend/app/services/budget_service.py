"""Budget persistence and live spending totals for one authenticated user."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    Date,
    Select,
    and_,
    cast,
    delete,
    func,
    literal_column,
    select,
    true,
    update,
)
from sqlalchemy.engine import MappingResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.sql import ColumnElement

from ..schemas import BudgetCreate, BudgetResponse, BudgetSummary, BudgetUpdate
from .expense_service import DEFAULT_LIMIT, MAX_LIMIT, MAX_SKIP

if TYPE_CHECKING:
    from ..models import Budget, Expense

BUDGET_CURRENCY = "PKR"  # Proposed currency policy for budgets without a currency column.
_UNIQUE_CONSTRAINTS = {"uq_budget_user_category_month_year", "uq_budgets_user_category_month_year"}
_PERIOD_FIELDS = {"category", "month", "year"}


class DuplicateBudgetError(Exception):
    """A budget already exists for the user, category, and period."""


class BudgetPeriodChangeError(ValueError):
    """The application has disabled changing the period through PATCH."""


class BudgetService:
    def __init__(
        self,
        db: Session,
        user_id: UUID,
        budget_model: type[Budget],
        expense_model: type[Expense],
        *,
        allow_period_changes: bool = True,
    ) -> None:
        if not isinstance(user_id, UUID):
            raise TypeError("BudgetService requires an authenticated user's UUID")
        self.db = db
        self.user_id = user_id
        self.budget_model = budget_model
        self.expense_model = expense_model
        self._allow_period_changes = allow_period_changes

    def create_budget(self, budget_data: BudgetCreate) -> BudgetResponse:
        with self._write():
            self._ensure_unique(budget_data.category, budget_data.month, budget_data.year)
            budget = self.budget_model(user_id=self.user_id, **budget_data.model_dump())
            self.db.add(budget)
            self.db.flush()
            return self._saved_response(budget.id)

    def get_budgets(
        self, skip: int = 0, limit: int = DEFAULT_LIMIT
    ) -> list[BudgetResponse]:
        if type(skip) is not int or not 0 <= skip <= MAX_SKIP:
            raise ValueError(f"skip must be an integer between 0 and {MAX_SKIP}")
        if type(limit) is not int or not 1 <= limit <= MAX_LIMIT:
            raise ValueError(f"limit must be an integer between 1 and {MAX_LIMIT}")

        budget = self.budget_model
        statement = (
            self._with_totals()
            .order_by(budget.year.desc(), budget.month.desc(), budget.id.desc())
            .offset(skip)
            .limit(limit)
        )
        rows = self.db.execute(statement).mappings()
        return [BudgetResponse.model_validate(row) for row in rows]

    def get_budget_by_id(self, budget_id: UUID) -> BudgetResponse | None:
        row = self._budget_result(budget_id).one_or_none()
        return BudgetResponse.model_validate(row) if row is not None else None

    def get_budgets_for_month(self, year: int, month: int) -> list[BudgetResponse]:
        budget = self.budget_model
        statement = self._with_totals().where(budget.year == year, budget.month == month)
        rows = self.db.execute(statement).mappings()
        return [BudgetResponse.model_validate(row) for row in rows]

    def update_budget(
        self, budget_id: UUID, budget_data: BudgetUpdate
    ) -> BudgetResponse | None:
        changes = budget_data.model_dump(
            exclude_unset=True, include=set(BudgetUpdate.model_fields)
        )
        if not self._allow_period_changes and {"month", "year"}.intersection(changes):
            raise BudgetPeriodChangeError("Budget month and year cannot be changed through PATCH")
        if not changes:
            return self.get_budget_by_id(budget_id)

        budget = self.budget_model
        statement = (
            update(budget)
            .where(self._owned_id(budget_id))
            .values(**changes)
            .returning(budget.category, budget.month, budget.year)
        )
        with self._write():
            period = self.db.execute(statement).one_or_none()
            if period is None:
                return None
            if _PERIOD_FIELDS.intersection(changes):
                # Use the effective period returned by the write, including omitted fields.
                self._ensure_unique(period.category, period.month, period.year, budget_id)
            # Re-read the same budget with its full calendar month's live expense total.
            return self._saved_response(budget_id)

    def delete_budget(self, budget_id: UUID) -> bool:
        budget = self.budget_model
        statement = delete(budget).where(self._owned_id(budget_id)).returning(budget.id)
        with self._write():
            return self.db.scalar(statement) is not None

    def get_budget_summary(self, budget_id: UUID) -> BudgetSummary | None:
        row = self._budget_result(budget_id).one_or_none()
        if row is None:
            return None
        return BudgetSummary.model_validate({**row, "budget_id": row["id"]})

    def _with_totals(self) -> Select:
        budget = self.budget_model
        expense = self.expense_model
        # transaction_date is a local calendar date. PostgreSQL computes the next
        # boundary, including January 10000 for the final supported budget month.
        month_start = func.make_date(budget.year, budget.month, 1)
        next_month = cast(month_start + literal_column("INTERVAL '1 month'"), Date)
        total = func.coalesce(func.sum(expense.amount), Decimal("0"))
        spending = (
            select(total.label("total_spent"))
            .where(
                expense.user_id == budget.user_id,
                expense.category == budget.category,
                expense.currency == BUDGET_CURRENCY,
                expense.transaction_date >= month_start,
                expense.transaction_date < next_month,
            )
            .correlate(budget)
            .lateral("spending")
        )
        return (
            select(
                budget.id,
                budget.user_id,
                budget.created_at,
                budget.category,
                budget.budget_limit,
                budget.month,
                budget.year,
                spending.c.total_spent,
                (budget.budget_limit - spending.c.total_spent).label("remaining_budget"),
            )
            .join_from(budget, spending, true())
            .where(budget.user_id == self.user_id)
        )

    def _budget_result(self, budget_id: UUID) -> MappingResult:
        statement = self._with_totals().where(self.budget_model.id == budget_id)
        return self.db.execute(statement).mappings()

    def _saved_response(self, budget_id: UUID) -> BudgetResponse:
        return BudgetResponse.model_validate(self._budget_result(budget_id).one())

    def _owned_id(self, budget_id: UUID) -> ColumnElement[bool]:
        budget = self.budget_model
        return and_(budget.user_id == self.user_id, budget.id == budget_id)

    def _ensure_unique(
        self, category: str, month: int, year: int, exclude_id: UUID | None = None
    ) -> None:
        budget = self.budget_model
        duplicate = select(budget.id).where(
            budget.user_id == self.user_id,
            budget.category == category,
            budget.month == month,
            budget.year == year,
        )
        if exclude_id is not None:
            duplicate = duplicate.where(budget.id != exclude_id)
        if self.db.scalar(select(duplicate.exists())):
            raise DuplicateBudgetError

    @contextmanager
    def _write(self) -> Iterator[None]:
        try:
            yield
            self.db.commit()
        except IntegrityError as error:
            self.db.rollback()
            original = error.orig
            code = getattr(original, "sqlstate", None) or getattr(original, "pgcode", None)
            constraint = getattr(getattr(original, "diag", None), "constraint_name", None)
            if code == "23505" and constraint in _UNIQUE_CONSTRAINTS:
                raise DuplicateBudgetError from error
            raise
        except Exception:
            self.db.rollback()
            raise
