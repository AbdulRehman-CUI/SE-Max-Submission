"""
app/models.py
─────────────
SQLAlchemy ORM models for SpendSense.

Models implemented:
  1. User    (table: users)
  2. Expense (table: expenses)
  3. Budget  (table: budgets)

Key Design Requirements:
  • UUID primary keys across all tables.
  • Numeric(12, 2) / Decimal for monetary calculations.
  • Date for expense transaction_date.
  • DateTime(timezone=True) for created_at (UTC).
  • Preserved canonical team field names:
    user_id, expense_id, budget_id, amount, category, description,
    transaction_date, currency, payment_method, budget_limit, month, year.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import relationship, synonym

from app.database import Base


def _utcnow() -> datetime:
    """Return the current UTC datetime (timezone-aware)."""
    return datetime.now(timezone.utc)


# ── User Model ────────────────────────────────────────────────────────────────
class User(Base):
    """Represents an application user."""

    __tablename__ = "users"

    id: uuid.UUID = Column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
        comment="Globally unique user identifier.",
    )
    username: str = Column(
        String(50),
        nullable=False,
        index=True,
        comment="Required username.",
    )
    email: str = Column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
        comment="Unique user email address.",
    )
    hashed_password: str = Column(
        String(255),
        nullable=False,
        comment="Hashed user password.",
    )
    is_active: bool = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Active status flag.",
    )
    created_at: datetime = Column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        comment="Timezone-aware creation timestamp (UTC).",
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    # User has many expenses
    expenses = relationship(
        "Expense",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    # User has many budgets
    budgets = relationship(
        "Budget",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    # Synonym for team naming rule compatibility
    user_id = synonym("id")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User id={self.id} username={self.username!r} email={self.email!r}>"


# ── Expense Model ─────────────────────────────────────────────────────────────
class Expense(Base):
    """Represents a financial transaction recorded by a user."""

    __tablename__ = "expenses"

    id: uuid.UUID = Column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
        comment="Globally unique expense identifier.",
    )
    user_id: uuid.UUID = Column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Foreign key referencing users.id.",
    )
    amount: Decimal = Column(
        Numeric(12, 2),
        nullable=False,
        comment="Expense amount, must be greater than zero.",
    )
    category: str = Column(
        String(100),
        nullable=False,
        index=True,
        comment="Expense category.",
    )
    description: Optional[str] = Column(
        String(255),
        nullable=True,
        comment="Optional description.",
    )
    transaction_date: date = Column(
        Date,
        nullable=False,
        index=True,
        comment="Date the transaction occurred.",
    )
    currency: str = Column(
        String(3),
        nullable=False,
        default="PKR",
        comment="Currency code, defaults to PKR.",
    )
    payment_method: Optional[str] = Column(
        String(50),
        nullable=True,
        comment="Optional payment method (e.g. Cash, Credit Card).",
    )
    created_at: datetime = Column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        comment="Timezone-aware creation timestamp (UTC).",
    )

    # ── Constraints & Indexes ─────────────────────────────────────────────────
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_expense_amount_positive"),
        Index("ix_expenses_user_id_transaction_date", "user_id", "transaction_date"),
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    # Expense belongs to one user
    user = relationship("User", back_populates="expenses")

    # Synonyms / property aliases for compatibility
    expense_id = synonym("id")

    @property
    def owner(self) -> User:
        return self.user

    @owner.setter
    def owner(self, value: User) -> None:
        self.user = value

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Expense id={self.id} user_id={self.user_id} amount={self.amount} category={self.category!r}>"


# ── Budget Model ──────────────────────────────────────────────────────────────
class Budget(Base):
    """Represents a monthly spending budget set by a user for a category."""

    __tablename__ = "budgets"

    id: uuid.UUID = Column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
        comment="Globally unique budget identifier.",
    )
    user_id: uuid.UUID = Column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Foreign key referencing users.id.",
    )
    category: str = Column(
        String(100),
        nullable=False,
        comment="Budget category.",
    )
    budget_limit: Decimal = Column(
        Numeric(12, 2),
        nullable=False,
        comment="Budget limit, must be non-negative.",
    )
    month: int = Column(
        Integer,
        nullable=False,
        comment="Budget month (1-12).",
    )
    year: int = Column(
        Integer,
        nullable=False,
        comment="Budget year.",
    )
    created_at: datetime = Column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        comment="Timezone-aware creation timestamp (UTC).",
    )

    # ── Constraints & Indexes ─────────────────────────────────────────────────
    __table_args__ = (
        CheckConstraint("budget_limit >= 0", name="ck_budget_limit_nonnegative"),
        CheckConstraint("month >= 1 AND month <= 12", name="ck_budget_month_range"),
        CheckConstraint("year >= 1 AND year <= 9999", name="ck_budget_year_range"),
        UniqueConstraint("user_id", "category", "month", "year", name="uq_budget_user_category_month_year"),
        Index("ix_budgets_user_id_year_month", "user_id", "year", "month"),
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    # Budget belongs to one user
    user = relationship("User", back_populates="budgets")

    # Synonyms / property aliases for compatibility
    budget_id = synonym("id")

    @property
    def owner(self) -> User:
        return self.user

    @owner.setter
    def owner(self, value: User) -> None:
        self.user = value

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Budget id={self.id} user_id={self.user_id} category={self.category!r} {self.month}/{self.year}>"
