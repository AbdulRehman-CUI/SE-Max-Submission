"""Expense HTTP endpoints and their integration point with the backend foundation."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import AfterValidator

from ..schemas import (
    ExpenseCreate,
    ExpenseParseRequest,
    ExpenseParseResponse,
    ExpenseResponse,
    ExpenseUpdate,
    SMSParseRequest,
    SMSParseResponse,
    validate_stored_money,
)
from ..services.ai_service import ExpenseAIService, ExpenseParsingError
from ..services.expense_service import (
    DEFAULT_LIMIT,
    MAX_LIMIT,
    MAX_SKIP,
    ExpenseService,
)

router = APIRouter(prefix="/expenses", tags=["expenses"])
_NOT_FOUND = "Expense not found"


def get_expense_service() -> ExpenseService:
    """Override with a provider that uses the shared JWT and session dependencies."""
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Expense service unavailable",
    )


ExpenseDependency = Annotated[ExpenseService, Depends(get_expense_service)]


def _validate_storage(payload: ExpenseCreate | ExpenseUpdate) -> ExpenseCreate | ExpenseUpdate:
    validate_stored_money(payload.amount)
    return payload


def get_expense_parser() -> ExpenseAIService:
    """Override with a provider that uses the shared JWT dependency."""
    raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Expense parsing is temporarily unavailable.")


@router.post("/parse")
async def parse_expense(
    request: ExpenseParseRequest,
    parser: Annotated[ExpenseAIService, Depends(get_expense_parser)],
) -> ExpenseParseResponse:
    try:
        return await parser.parse_expense(request)
    except ExpenseParsingError as error:
        raise HTTPException(error.status_code, error.detail) from None


@router.post("/parse-sms")
async def parse_sms(
    request: SMSParseRequest,
    parser: Annotated[ExpenseAIService, Depends(get_expense_parser)],
) -> SMSParseResponse:
    try:
        return await parser.parse_sms(request)
    except ExpenseParsingError as error:
        raise HTTPException(error.status_code, error.detail) from None


@router.post("", status_code=status.HTTP_201_CREATED)
def create_expense(
    expense_data: Annotated[ExpenseCreate, AfterValidator(_validate_storage)],
    service: ExpenseDependency,
) -> ExpenseResponse:
    return service.create_expense(expense_data)


@router.get("")
def get_expenses(
    service: ExpenseDependency,
    skip: Annotated[int, Query(ge=0, le=MAX_SKIP)] = 0,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
) -> list[ExpenseResponse]:
    return service.get_expenses(skip=skip, limit=limit)


@router.get("/{expense_id}")
def get_expense(expense_id: UUID, service: ExpenseDependency) -> ExpenseResponse:
    return _require_expense(service.get_expense_by_id(expense_id))


@router.put("/{expense_id}")
@router.patch("/{expense_id}")
def update_expense(
    expense_id: UUID,
    expense_data: Annotated[ExpenseUpdate, AfterValidator(_validate_storage)],
    service: ExpenseDependency,
) -> ExpenseResponse:
    return _require_expense(service.update_expense(expense_id, expense_data))


@router.delete("/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_expense(expense_id: UUID, service: ExpenseDependency) -> Response:
    if not service.delete_expense(expense_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _require_expense(expense: ExpenseResponse | None) -> ExpenseResponse:
    if expense is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND)
    return expense
