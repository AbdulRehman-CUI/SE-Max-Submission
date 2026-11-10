"""Expense persistence scoped to one authenticated user and request session."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import and_, delete, select, update
from sqlalchemy.orm import Session
from sqlalchemy.sql import ColumnElement

from ..schemas import ExpenseCreate, ExpenseResponse, ExpenseUpdate

if TYPE_CHECKING:
    from ..models import Expense

DEFAULT_LIMIT = 20
MAX_LIMIT = 100
MAX_SKIP = 2**63 - 1  # PostgreSQL represents OFFSET as a signed bigint.


class ExpenseService:
    def __init__(
        self, db: Session, user_id: UUID, expense_model: type[Expense]
    ) -> None:
        if not isinstance(user_id, UUID):
            raise TypeError("ExpenseService requires an authenticated user's UUID")
        self.db = db
        self.user_id = user_id
        self.expense_model = expense_model

    def create_expense(self, expense_data: ExpenseCreate) -> ExpenseResponse:
        with self._write():
            fields = expense_data.model_dump()
            expense = self.expense_model(user_id=self.user_id, **fields)
            self.db.add(expense)
            self.db.flush()
            return ExpenseResponse.model_validate(expense)

    def get_expenses(
        self, skip: int = 0, limit: int = DEFAULT_LIMIT
    ) -> list[ExpenseResponse]:
        if type(skip) is not int or not 0 <= skip <= MAX_SKIP:
            raise ValueError(f"skip must be an integer between 0 and {MAX_SKIP}")
        if type(limit) is not int or not 1 <= limit <= MAX_LIMIT:
            raise ValueError(f"limit must be an integer between 1 and {MAX_LIMIT}")

        model = self.expense_model
        statement = (
            select(model)
            .where(model.user_id == self.user_id)
            .order_by(model.transaction_date.desc(), model.id.desc())
            .offset(skip)
            .limit(limit)
        )
        expenses = self.db.scalars(statement)
        return [ExpenseResponse.model_validate(expense) for expense in expenses]

    def get_expense_by_id(self, expense_id: UUID) -> ExpenseResponse | None:
        statement = select(self.expense_model).where(self._owned_id(expense_id))
        expense = self.db.scalars(statement).one_or_none()
        return ExpenseResponse.model_validate(expense) if expense is not None else None

    def update_expense(
        self, expense_id: UUID, expense_data: ExpenseUpdate
    ) -> ExpenseResponse | None:
        changes = expense_data.model_dump(
            exclude_unset=True, include=set(ExpenseUpdate.model_fields)
        )
        if not changes:
            return self.get_expense_by_id(expense_id)

        model = self.expense_model
        statement = (
            update(model)
            .where(self._owned_id(expense_id))
            .values(**changes)
            .returning(model)
        )
        with self._write():
            expense = self.db.scalars(
                statement, execution_options={"populate_existing": True}
            ).one_or_none()
            if expense is None:
                return None
            return ExpenseResponse.model_validate(expense)

    def delete_expense(self, expense_id: UUID) -> bool:
        model = self.expense_model
        statement = delete(model).where(self._owned_id(expense_id)).returning(model.id)
        with self._write():
            return self.db.scalar(statement) is not None

    def _owned_id(self, expense_id: UUID) -> ColumnElement[bool]:
        model = self.expense_model
        return and_(model.user_id == self.user_id, model.id == expense_id)

    @contextmanager
    def _write(self) -> Iterator[None]:
        # The session may already have a read transaction from authentication.
        try:
            yield
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
