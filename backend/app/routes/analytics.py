from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.routes.auth import get_current_user
from app.services.ai_service import AIService
from app.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["Analytics"])


class SummaryResponse(BaseModel):
    total_spent: Decimal
    total_transactions: int
    average_transaction: Decimal
    current_month_spending: Decimal
    previous_month_spending: Decimal
    spending_change_percentage: Decimal


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
    year: Optional[int] = Query(None, ge=2000),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    return AnalyticsService.get_monthly(user_id=current_user.id, db=db, year=year)


@router.get("/budget-status", response_model=List[BudgetStatusResponse])
def get_budget_status(
    month: Optional[int] = Query(None, ge=1, le=12),
    year: Optional[int] = Query(None, ge=2000),
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


@router.get("/insights", response_model=InsightsResponse)
def get_insights(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    summary = AnalyticsService.get_summary(user_id=current_user.id, db=db)
    categories = AnalyticsService.get_categories(user_id=current_user.id, db=db)
    category_budgets = AnalyticsService.get_budget_status(user_id=current_user.id, db=db)
    anomalies = AnalyticsService.detect_anomalies(user_id=current_user.id, db=db)

    payload = {
        "total_spent": summary.get("total_spent", Decimal("0.00")),
        "total_transactions": summary.get("total_transactions", 0),
        "average_transaction": summary.get("average_transaction", Decimal("0.00")),
        "current_month_spending": summary.get("current_month_spending", Decimal("0.00")),
        "previous_month_spending": summary.get("previous_month_spending", Decimal("0.00")),
        "spending_change_percentage": summary.get("spending_change_percentage", Decimal("0.00")),
        "categories": categories,
        "budgets": category_budgets,
        "anomalies": anomalies.get("anomalies", []),
    }
    response = AIService.get_insights(payload)
    response["user_id"] = current_user.id
    return response
