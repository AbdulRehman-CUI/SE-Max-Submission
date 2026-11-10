"""Analytics router for explicit registration after Developer 1 approves the contract."""

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import Field

from ..schemas import BudgetResponse, _ExpenseAmount
from ..services.budget_service import BUDGET_CURRENCY, BudgetService
from ..services.financial_insights_service import FinancialInsightsResponse, FinancialInsightsService
from ..services.spending_analytics_service import AnalyticsInputError, SpendingAnalyticsService
from ..spending_analytics_schemas import (
    AnomalyCandidate, AnomalyResult, CategorySpending, MonthlySpendingSummary, MonthlySpendingTrend,
)
from .budgets import get_budget_service

router = APIRouter(prefix="/analytics", tags=["analytics"])
Year = Annotated[int, Query(ge=1, le=9999)]
Month = Annotated[int, Query(ge=1, le=12)]


class AnomalyCheckRequest(AnomalyCandidate):
    amount: Annotated[_ExpenseAmount, Field(max_digits=512, decimal_places=128)]


def get_spending_analytics() -> SpendingAnalyticsService:
    """Bind the actual authenticated user and shared request session in composition."""
    raise HTTPException(503, "Spending analytics is temporarily unavailable.")


def get_financial_insights() -> FinancialInsightsService:
    """Use the shared Gemini adapter when configured, or deterministic insights."""
    return FinancialInsightsService()


Analytics = Annotated[SpendingAnalyticsService, Depends(get_spending_analytics)]


@router.get("/monthly")
def monthly(year: Year, month: Month, analytics: Analytics) -> MonthlySpendingSummary:
    try:
        return analytics.monthly(year, month)
    except AnalyticsInputError as error:
        raise HTTPException(422, str(error)) from None


@router.get("/categories")
def categories(year: Year, month: Month, analytics: Analytics) -> list[CategorySpending]:
    return monthly(year, month, analytics).categories


@router.get("/trends")
def trends(
    analytics: Analytics,
    months: Annotated[int, Query(ge=1, le=120)] = 3,
    end_month: date | None = None,
) -> list[MonthlySpendingTrend]:
    try:
        return analytics.trends(months, end_month=end_month)
    except AnalyticsInputError as error:
        raise HTTPException(422, str(error)) from None


@router.post("/anomalies/check")
def check_anomaly(candidate: AnomalyCheckRequest, analytics: Analytics) -> AnomalyResult:
    try:
        return analytics.check_anomaly(candidate)
    except AnalyticsInputError as error:
        raise HTTPException(422, str(error)) from None


@dataclass(frozen=True)
class InsightInputs:
    month: MonthlySpendingTrend
    budgets: list[BudgetResponse]
    anomaly: AnomalyResult | None


def collect_insight_inputs(
    year: Year,
    month: Month,
    analytics: Analytics,
    budgets: Annotated[BudgetService, Depends(get_budget_service)],
) -> InsightInputs:
    reference = datetime.now(timezone.utc)
    try:
        report = analytics.trends(
            1 if (year, month) == (1, 1) else 2,
            end_month=date(year, month, 1), reference_datetime=reference,
        )[-1]
        anomaly = analytics.latest_anomaly(report, reference_datetime=reference)
    except AnalyticsInputError as error:
        raise HTTPException(422, str(error)) from None
    budget_rows = budgets.get_budgets_for_month(year, month) if report.currency == BUDGET_CURRENCY else []
    if any(row.user_id != analytics.user_id for row in budget_rows):
        raise RuntimeError("Budget provider returned another user's data")
    return InsightInputs(report, budget_rows, anomaly)


@router.get("/insights")
async def insights(
    inputs: Annotated[InsightInputs, Depends(collect_insight_inputs)],
    generator: Annotated[FinancialInsightsService, Depends(get_financial_insights)],
) -> FinancialInsightsResponse:
    return await generator.generate(inputs.month, budgets=inputs.budgets, anomaly=inputs.anomaly)
