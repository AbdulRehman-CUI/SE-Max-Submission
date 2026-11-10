"""Provisional analytics contracts for Developer 1's review."""

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from .schemas import _BudgetLimit, _Currency, _ExpenseAmount, _Money, _Request, _Text, _TransactionDate


class CategorySpending(BaseModel):
    category: str | None
    total_spent: Decimal
    transaction_count: int
    percentage_of_total: Decimal


class MonthlySpendingSummary(BaseModel):
    year: int
    month: int
    currency: str
    total_spent: Decimal
    transaction_count: int
    average_expense: Decimal | None
    categories: list[CategorySpending]
    is_partial: bool
    through_date: date


class MonthlySpendingTrend(MonthlySpendingSummary):
    change_amount: Decimal | None
    change_percentage: Decimal | None


class AnomalyCandidate(_Request):
    amount: _ExpenseAmount
    category: _Text
    transaction_date: _TransactionDate
    currency: _Currency = "PKR"


class AnomalyPolicy(_Request):
    model_config = ConfigDict(frozen=True)

    baseline_method: Literal["median", "mean"] = "median"
    minimum_history: Annotated[int, Field(strict=True, gt=0)] = 5
    threshold_multiplier: Annotated[_Money, Field(ge=1)] = Decimal("3")
    minimum_amount: _BudgetLimit = Decimal("1000")


class AnomalyResult(BaseModel):
    expense_id: UUID | None
    status: Literal["insufficient_history", "unavailable_baseline", "normal", "unusual"]
    is_unusual: bool
    has_enough_history: bool
    category: str
    currency: str
    amount: Decimal
    sample_count: int
    minimum_history: int
    baseline_method: Literal["median", "mean"]
    baseline_amount: Decimal | None
    threshold_amount: Decimal | None
    threshold_multiplier: Decimal
    minimum_amount: Decimal
    explanation: str
