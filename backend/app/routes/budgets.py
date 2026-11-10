from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Budget, User
from app.routes.auth import get_current_user

router = APIRouter(prefix="/budgets", tags=["Budgets"])


class BudgetCreate(BaseModel):
    category: str = Field(..., min_length=1, max_length=100)
    budget_limit: Decimal = Field(..., gt=0)
    month: int = Field(..., ge=1, le=12)
    year: int = Field(..., ge=2000)


class BudgetUpdate(BaseModel):
    category: Optional[str] = Field(None, min_length=1, max_length=100)
    budget_limit: Optional[Decimal] = Field(None, gt=0)
    month: Optional[int] = Field(None, ge=1, le=12)
    year: Optional[int] = Field(None, ge=2000)


class BudgetResponse(BaseModel):
    id: uuid.UUID
    budget_id: uuid.UUID
    user_id: uuid.UUID
    category: str
    budget_limit: Decimal
    month: int
    year: int
    created_at: datetime

    model_config = {"from_attributes": True}


@router.post("", response_model=BudgetResponse, status_code=status.HTTP_201_CREATED)
def create_budget(
    payload: BudgetCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Budget:
    existing = (
        db.query(Budget)
        .filter(
            Budget.user_id == current_user.id,
            Budget.category == payload.category,
            Budget.month == payload.month,
            Budget.year == payload.year,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Budget already exists for this category, month, and year.",
        )

    budget = Budget(
        user_id=current_user.id,
        category=payload.category,
        budget_limit=payload.budget_limit,
        month=payload.month,
        year=payload.year,
    )
    db.add(budget)
    db.commit()
    db.refresh(budget)
    return budget


@router.get("", response_model=List[BudgetResponse])
def list_budgets(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[Budget]:
    return (
        db.query(Budget)
        .filter(Budget.user_id == current_user.id)
        .order_by(Budget.year.desc(), Budget.month.desc())
        .all()
    )


@router.get("/{budget_id}", response_model=BudgetResponse)
def get_budget(
    budget_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Budget:
    budget = (
        db.query(Budget)
        .filter(Budget.id == budget_id, Budget.user_id == current_user.id)
        .first()
    )
    if not budget:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Budget not found.",
        )
    return budget


@router.put("/{budget_id}", response_model=BudgetResponse)
def update_budget(
    budget_id: uuid.UUID,
    payload: BudgetUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Budget:
    budget = (
        db.query(Budget)
        .filter(Budget.id == budget_id, Budget.user_id == current_user.id)
        .first()
    )
    if not budget:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Budget not found.",
        )
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(budget, field, value)
    db.commit()
    db.refresh(budget)
    return budget


@router.delete("/{budget_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_budget(
    budget_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    budget = (
        db.query(Budget)
        .filter(Budget.id == budget_id, Budget.user_id == current_user.id)
        .first()
    )
    if not budget:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Budget not found.",
        )
    db.delete(budget)
    db.commit()

