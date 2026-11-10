from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Annotated, Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.routes.auth import get_current_user
from app.services.analytics_service import AnalyticsService
from app.services.budget_service import BudgetService
from app.services.financial_insights_service import FinancialInsightsService
from .budgets import get_budget_service
from .provisional_analytics import Analytics, InsightInputs, collect_insight_inputs, get_financial_insights

router = APIRouter(prefix="/analytics", tags=["Analytics"])


class SummaryResponse(BaseModel):
    total_spent: Decimal
    total_transactions: int
    average_transaction: Decimal
    current_month_spending: Decimal
    previous_month_spending: Decimal
    spending_change_percentage: Decimal | None
    is_partial: bool
    through_date: date


class CategoryAnalyticsResponse(BaseModel):
    category: str
    total_spent: Decimal
    transaction_count: int
    percentage_of_total: Decimal


class MonthlyAnalyticsResponse(BaseModel):
    year: int
    month: int
    total_spent: Decimal
    transaction_count: int


class BudgetStatusResponse(BaseModel):
    category: str
    budget_limit: Decimal
    total_spent: Decimal
    remaining_budget: Decimal
    utilization_percentage: Decimal


class AnomalyResponse(BaseModel):
    user_id: uuid.UUID
    anomalies: List[Dict[str, Any]]
    total_anomalies: int


class InsightItem(BaseModel):
    type: str
    title: str
    message: str
    priority: str


class InsightsResponse(BaseModel):
    user_id: uuid.UUID
    insights: List[InsightItem]
    generated_at: str
    status: str


@router.get("/summary", response_model=SummaryResponse)
def get_spending_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    return AnalyticsService.get_summary(user_id=current_user.id, db=db)


@router.get("/categories", response_model=List[CategoryAnalyticsResponse])
def get_category_analytics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    return AnalyticsService.get_categories(user_id=current_user.id, db=db)


@router.get("/monthly", response_model=List[MonthlyAnalyticsResponse])
def get_monthly_analytics(
    year: Optional[int] = Query(None, ge=1, le=9999),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    return AnalyticsService.get_monthly(user_id=current_user.id, db=db, year=year)


@router.get("/budget-status", response_model=List[BudgetStatusResponse])
def get_budget_status(
    month: Optional[int] = Query(None, ge=1, le=12),
    year: Optional[int] = Query(None, ge=1, le=9999),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    return AnalyticsService.get_budget_status(
        user_id=current_user.id,
        db=db,
        month=month,
        year=year,
    )


@router.get("/anomalies", response_model=AnomalyResponse)
def get_anomalies(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    return AnalyticsService.detect_anomalies(user_id=current_user.id, db=db)


def _current_insight_inputs(
    analytics: Analytics,
    budgets: Annotated[BudgetService, Depends(get_budget_service)],
) -> InsightInputs:
    today = datetime.now(ZoneInfo("Asia/Karachi")).date()
    return collect_insight_inputs(today.year, today.month, analytics, budgets)


@router.get("/insights", response_model=InsightsResponse)
async def get_insights(
    current_user: Annotated[User, Depends(get_current_user)],
    inputs: Annotated[InsightInputs, Depends(_current_insight_inputs)],
    generator: Annotated[FinancialInsightsService, Depends(get_financial_insights)],
) -> Dict[str, Any]:
    result = await generator.generate(inputs.month, budgets=inputs.budgets, anomaly=inputs.anomaly)
    legacy_type = {
        "category": "category_spending", "trend": "spending_trend", "budget": "budget_utilization",
        "anomaly": "unusual_spending", "awareness": "savings_control",
    }
    return {
        "user_id": current_user.id,
        "insights": [
            {"type": "spending_trend", "title": "Spending pattern", "message": result.summary, "priority": "medium"},
            *[
                {"type": legacy_type[item.type], "title": item.title, "message": item.message,
                 "priority": "high" if item.severity == "warning" else "medium"}
                for item in [*result.warnings, *result.insights]
            ],
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "fallback" if result.is_fallback else "success",
    }
