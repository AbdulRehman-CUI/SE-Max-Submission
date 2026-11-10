"""
app/database.py
───────────────
Single SQLAlchemy engine + session factory for the entire application.

Rules enforced here:
  • One engine, one SessionLocal – do NOT create another anywhere else.
  • Credentials come exclusively from settings.DATABASE_URL.
  • get_db() is the FastAPI dependency; use it in route parameters only.
"""
from __future__ import annotations

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session
from typing import Generator, Tuple

from app.config import settings


# ── Engine ────────────────────────────────────────────────────────────────────
engine = create_engine(
    settings.DATABASE_URL,
    # Keep a small pool; tune via environment if needed.
    pool_pre_ping=True,       # Discard stale connections silently.
    pool_size=5,
    max_overflow=10,
    echo=settings.DEBUG,      # Log SQL only when DEBUG=True.
)


# ── Session factory ───────────────────────────────────────────────────────────
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)


# ── Declarative base (all models inherit from this) ───────────────────────────
class Base(DeclarativeBase):
    """Shared declarative base.  Import from here, not from sqlalchemy directly."""
    pass


# ── FastAPI dependency ────────────────────────────────────────────────────────
def get_db() -> Generator[Session, None, None]:
    """Yield a database session and guarantee it is closed after the request."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db_connection() -> Tuple[bool, str]:
    """Verify database connectivity by executing SELECT 1 with the engine.

    Returns:
        (True, "Database connection successful") if connectivity check passes.
        (False, error_message) if connection fails. Never exposes credentials.
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True, "Database connection successful"
    except Exception as exc:
        # Gracefully handle failures without leaking credentials in DATABASE_URL
        err_type = type(exc).__name__
        return False, f"Database connectivity check failed: {err_type}"


