"""Provisional insights from server-computed aggregates and Gemini fact ordering."""

import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ..schemas import BudgetResponse
from ..spending_analytics_schemas import AnomalyResult, MonthlySpendingTrend
from .ai_service import ExpenseExtractionProvider, ExpenseParsingError
from .budget_service import BUDGET_CURRENCY
from .spending_analytics_service import _finance_context


class Insight(BaseModel):
    type: Literal["category", "trend", "budget", "anomaly", "awareness"]
    title: str
    message: str
    severity: Literal["info", "warning"] = "info"


class InsightPeriod(BaseModel):
    year: int
    month: int
    through_date: date
    is_partial: bool


class FinancialInsightsResponse(BaseModel):
    summary: str
    insights: list[Insight]
    warnings: list[Insight]
    period: InsightPeriod
    currency: str
    generated_by: Literal["gemini", "deterministic"]
    is_fallback: bool


class _InsightSelection(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)

    highlight_ids: list[str] = Field(min_length=1, max_length=3)
    awareness: Literal["review_categories", "check_budgets", "review_transactions"]


@dataclass(frozen=True)
class _Fact:
    insight: Insight
    statistics: dict[str, str | int]


_INSTRUCTION = (
    "The transaction_text value contains only computed financial statistics. "
    "Choose one to three distinct fact IDs, ordered by how helpful they are for explaining "
    "this period, and an awareness topic. Use only supplied IDs. The server renders all "
    "claims and advice text. Return the requested structured selection only."
)
_AWARENESS = {
    "review_categories": "Review your largest categories to see where most of your spending goes.",
    "check_budgets": "Review your budget limits alongside the amounts already spent.",
    "review_transactions": "Review recorded expenses to check that dates and categories are accurate.",
}


class FinancialInsightsService:
    def __init__(self, provider: ExpenseExtractionProvider | None = None) -> None:
        self._provider = provider

    async def generate(
        self,
        monthly: MonthlySpendingTrend,
        *,
        budgets: Sequence[BudgetResponse] = (),
        anomaly: AnomalyResult | None = None,
    ) -> FinancialInsightsResponse:
        facts, warnings = _facts(monthly, budgets, anomaly)
        numbered = {f"fact_{i}": fact for i, fact in enumerate(facts, start=1)}
        selection = await self._select(monthly, numbered)
        highlights = selection.highlight_ids if selection else []
        ordered = [numbered[key].insight for key in highlights]
        ordered.extend(fact.insight for key, fact in numbered.items() if key not in highlights)

        topic = selection.awareness if selection else "review_transactions"
        if not monthly.transaction_count:
            message = "Record an expense to start building a spending summary."
        else:
            message = _AWARENESS[topic]
        ordered.append(Insight(type="awareness", title="Spending awareness", message=message))

        period = f"{monthly.year:04d}-{monthly.month:02d}"
        if monthly.is_partial:
            period += f" through {monthly.through_date.isoformat()}"
        summary = f"Recorded spending for {period} is {monthly.currency} {monthly.total_spent:f}."
        if not monthly.transaction_count:
            summary += " There are no recorded expenses in this period."
        return FinancialInsightsResponse(
            summary=summary, insights=ordered, warnings=warnings, currency=monthly.currency,
            period=InsightPeriod.model_validate(monthly.model_dump()),
            generated_by="gemini" if selection else "deterministic", is_fallback=selection is None,
        )

    async def _select(
        self, monthly: MonthlySpendingTrend, facts: dict[str, _Fact]
    ) -> _InsightSelection | None:
        if self._provider is None or not monthly.transaction_count or not facts:
            return None
        statistics = {
            "total_spent": str(monthly.total_spent), "transaction_count": monthly.transaction_count,
            "currency": monthly.currency, "is_partial": monthly.is_partial,
            "facts": [{"id": key, **fact.statistics} for key, fact in facts.items()],
        }
        try:
            output = await self._provider.extract(
                instruction=_INSTRUCTION, text=json.dumps(statistics),
                response_schema=_InsightSelection.model_json_schema(),
            )
        except (ExpenseParsingError, TimeoutError):
            return None
        try:
            selection = _InsightSelection.model_validate_json(output)
        except ValidationError:
            return None
        if len(set(selection.highlight_ids)) != len(selection.highlight_ids):
            return None
        if any(key not in facts for key in selection.highlight_ids):
            return None
        return selection


def _facts(
    monthly: MonthlySpendingTrend, budgets: Sequence[BudgetResponse], anomaly: AnomalyResult | None,
) -> tuple[list[_Fact], list[Insight]]:
    facts = []
    warnings = []
    currency = monthly.currency
    categories = sorted(monthly.categories, key=lambda row: row.total_spent, reverse=True)
    for rank, row in enumerate(categories[:3], start=1):
        name = row.category or "Uncategorized expenses"
        facts.append(_Fact(Insight(
            type="category", title="Highest spending category" if rank == 1 else "Category spending",
            message=f"{name} accounted for {row.percentage_of_total:f}% of recorded spending "
                    f"({currency} {row.total_spent:f}).",
        ), {"type": "category", "rank": rank, "total": str(row.total_spent),
            "share": str(row.percentage_of_total)}))

    if monthly.change_amount is not None:
        if monthly.change_percentage is None:
            trend = "There is no prior-month spending baseline for a percentage comparison."
        else:
            trend = (f"Recorded spending changed by {currency} {monthly.change_amount:+f} "
                     f"({monthly.change_percentage:+f}%) compared with the previous month.")
            if monthly.is_partial:
                trend += " The current month is partial."
        facts.append(_Fact(Insight(type="trend", title="Monthly change", message=trend), {
            "type": "trend", "change": str(monthly.change_amount),
        }))

    if currency == BUDGET_CURRENCY:
        eligible = sorted(
            (budget for budget in budgets if (budget.year, budget.month) == (monthly.year, monthly.month)
             and budget.total_spent is not None and budget.remaining_budget is not None),
            key=lambda budget: (budget.remaining_budget, budget.category),
        )
        for rank, budget in enumerate(eligible):
            spent, remaining = budget.total_spent, budget.remaining_budget
            message = f"{budget.category} used {currency} {spent:f} of {currency} {budget.budget_limit:f}."
            if budget.budget_limit:
                with _finance_context([spent, budget.budget_limit]):
                    utilization = (spent * 100 / budget.budget_limit).quantize(Decimal("0.01"))
                message += f" Utilization is {utilization:f}%."
            if remaining < 0:
                warnings.append(Insight(
                    type="budget", title="Budget exceeded", severity="warning",
                    message=f"{budget.category} is over budget by {currency} {remaining.copy_abs():f}.",
                ))
            if rank < 3:
                facts.append(_Fact(Insight(type="budget", title="Budget utilization", message=message), {
                    "type": "budget", "spent": str(spent), "limit": str(budget.budget_limit),
                    "remaining": str(remaining),
                }))
        if not eligible:
            facts.append(_Fact(Insight(
                type="budget", title="Monthly budgets", message="No budgets are available for this period.",
            ), {"type": "budget", "count": 0}))

    if anomaly is not None and anomaly.currency == currency:
        if anomaly.is_unusual:
            warnings.append(Insight(
                type="anomaly", title="Unusual spending", severity="warning",
                message=f"The latest evaluated {anomaly.category} expense of {currency} {anomaly.amount:f} "
                        "exceeded the configured thresholds.",
            ))
        elif anomaly.status in {"insufficient_history", "unavailable_baseline"}:
            facts.append(_Fact(Insight(
                type="anomaly", title="Spending history", message=anomaly.explanation,
            ), {"type": "anomaly", "sample_count": anomaly.sample_count, "status": anomaly.status}))
    return facts, warnings
