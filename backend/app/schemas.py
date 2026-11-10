"""Proposed Phase 1 API schemas for expenses, budgets, and parsing drafts."""

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal, TypeVar
from uuid import UUID

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StringConstraints,
    computed_field,
)
from pydantic.json_schema import SkipJsonSchema


def _exact_money(value: object) -> object:
    if not isinstance(value, (str, int, Decimal)) or isinstance(value, bool):
        raise ValueError("Use a decimal string or an integer for monetary values")
    return value


def _require_value(value: object) -> object:
    if value is None:
        raise ValueError("Omit this field to leave it unchanged")
    return value


def _calendar_date(value: object) -> object:
    if isinstance(value, str):
        parsed = date.fromisoformat(value)
        if parsed.isoformat() != value:
            raise ValueError("Use YYYY-MM-DD for transaction_date")
        return parsed
    return value


_T = TypeVar("_T")
# Pydantic skips validation for omitted defaults and validates an explicit null.
_PatchValue = Annotated[
    _T | SkipJsonSchema[None],
    Field(default_factory=lambda: None),
    AfterValidator(_require_value),
]
_Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
_Currency = Annotated[
    str, StringConstraints(strip_whitespace=True, pattern=r"^[A-Za-z]{3}$", to_upper=True)
]
_FiniteDecimal = Annotated[Decimal, Field(allow_inf_nan=False)]
_ExactMoney = BeforeValidator(_exact_money, json_schema_input_type=str | int)
_Money = Annotated[_FiniteDecimal, _ExactMoney]
_ExpenseAmount = Annotated[_FiniteDecimal, Field(gt=0), _ExactMoney]
_BudgetLimit = Annotated[_FiniteDecimal, Field(ge=0), _ExactMoney]
_TransactionDate = Annotated[date, Field(strict=True), BeforeValidator(_calendar_date)]
_Month = Annotated[int, Field(strict=True, ge=1, le=12)]
_Year = Annotated[int, Field(strict=True, ge=date.min.year, le=date.max.year)]


class _Request(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ExpenseCreate(_Request):
    amount: _ExpenseAmount
    category: _Text
    description: _Text | None = None
    transaction_date: _TransactionDate
    currency: _Currency = "PKR"
    payment_method: _Text | None = None


class ExpenseUpdate(_Request):
    amount: _PatchValue[_ExpenseAmount]
    category: _PatchValue[_Text]
    description: _Text | None = None
    transaction_date: _PatchValue[_TransactionDate]
    currency: _PatchValue[_Currency]
    payment_method: _Text | None = None


class _PersistedResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    created_at: AwareDatetime


class ExpenseResponse(_PersistedResponse):
    amount: _ExpenseAmount
    category: _Text
    description: _Text | None
    transaction_date: _TransactionDate
    currency: _Currency
    payment_method: _Text | None


class BudgetCreate(_Request):
    category: _Text
    budget_limit: _BudgetLimit
    month: _Month
    year: _Year


class BudgetUpdate(_Request):
    category: _PatchValue[_Text]
    budget_limit: _PatchValue[_BudgetLimit]
    month: _PatchValue[_Month]
    year: _PatchValue[_Year]


class BudgetResponse(_PersistedResponse):
    category: _Text
    budget_limit: _BudgetLimit
    month: _Month
    year: _Year
    total_spent: _BudgetLimit | None = None
    remaining_budget: _Money | None = None


class BudgetSummary(BaseModel):
    budget_id: UUID
    category: _Text
    month: _Month
    year: _Year
    budget_limit: _BudgetLimit
    total_spent: _BudgetLimit
    remaining_budget: _Money


class _ExpenseDraft(BaseModel):
    amount: _ExpenseAmount | None = None
    category: _Text | None = None
    description: _Text | None = None
    transaction_date: _TransactionDate | None = None
    currency: _Currency | None = None
    payment_method: _Text | None = None


class ExpenseParseRequest(_Request):
    text: _Text


class ExpenseParseResponse(BaseModel):
    extracted_fields: _ExpenseDraft
    confirmation_required: Literal[True] = True

    @computed_field
    @property
    def missing_fields(self) -> list[str]:
        return [
            name
            for name, field in ExpenseCreate.model_fields.items()
            if field.is_required() and getattr(self.extracted_fields, name) is None
        ]


class SMSParseRequest(ExpenseParseRequest):
    """Pasted wallet or bank transaction text."""


SMSTransactionType = Literal[
    "debit", "credit", "incoming_transfer", "outgoing_transfer", "own_account_transfer",
    "merchant_payment", "atm_withdrawal", "bill_payment", "mobile_top_up",
    "wallet_payment", "balance_notification", "unknown",
]
SMSTransactionStatus = Literal["completed", "failed", "reversed", "pending", "unknown"]


class SMSParseResponse(ExpenseParseResponse):
    """Transaction metadata and, when eligible, an expense draft for review."""

    transaction_type: SMSTransactionType = "unknown"
    transaction_status: SMSTransactionStatus = "unknown"
    amount: _ExpenseAmount | None = None
    currency: _Currency | None = None
    transaction_date: _TransactionDate | None = None
    merchant: _Text | None = None
    transaction_reference: _Text | None = None
    source: _Text | None = None
    is_expense_candidate: bool = False
    clarification_required: bool = False
