"""Budget HTTP endpoints and the shared backend integration point."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import AfterValidator

from ..schemas import BudgetCreate, BudgetResponse, BudgetSummary, BudgetUpdate, validate_stored_money
from ..services.budget_service import BudgetPeriodChangeError, BudgetService, DuplicateBudgetError
from ..services.expense_service import DEFAULT_LIMIT, MAX_LIMIT, MAX_SKIP

router = APIRouter(prefix="/budgets", tags=["budgets"])
_NOT_FOUND = "Budget not found"
_DUPLICATE = "A budget already exists for this category and period"


def get_budget_service() -> BudgetService:
    """Override with a provider that uses the shared JWT and session dependencies."""
    raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Budget service unavailable")


BudgetDependency = Annotated[BudgetService, Depends(get_budget_service)]


def _validate_storage(payload: BudgetCreate | BudgetUpdate) -> BudgetCreate | BudgetUpdate:
    validate_stored_money(payload.budget_limit)
    return payload


@router.post("", status_code=status.HTTP_201_CREATED)
def create_budget(
    budget_data: Annotated[BudgetCreate, AfterValidator(_validate_storage)],
    service: BudgetDependency,
) -> BudgetResponse:
    try:
        return service.create_budget(budget_data)
    except DuplicateBudgetError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, _DUPLICATE) from error


@router.get("")
def get_budgets(
    service: BudgetDependency,
    skip: Annotated[int, Query(ge=0, le=MAX_SKIP)] = 0,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
) -> list[BudgetResponse]:
    return service.get_budgets(skip=skip, limit=limit)


@router.get("/{budget_id}")
def get_budget(budget_id: UUID, service: BudgetDependency) -> BudgetResponse:
    budget = service.get_budget_by_id(budget_id)
    if budget is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _NOT_FOUND)
    return budget


@router.put("/{budget_id}")
@router.patch("/{budget_id}")
def update_budget(
    budget_id: UUID,
    budget_data: Annotated[BudgetUpdate, AfterValidator(_validate_storage)],
    service: BudgetDependency,
) -> BudgetResponse:
    try:
        budget = service.update_budget(budget_id, budget_data)
    except BudgetPeriodChangeError as error:
        raise HTTPException(422, str(error)) from error
    except DuplicateBudgetError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, _DUPLICATE) from error
    if budget is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _NOT_FOUND)
    return budget


@router.delete("/{budget_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_budget(budget_id: UUID, service: BudgetDependency) -> Response:
    if not service.delete_budget(budget_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, _NOT_FOUND)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{budget_id}/summary")
def get_budget_summary(budget_id: UUID, service: BudgetDependency) -> BudgetSummary:
    summary = service.get_budget_summary(budget_id)
    if summary is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _NOT_FOUND)
    return summary
