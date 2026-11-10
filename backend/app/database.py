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

from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session
from typing import Generator, Tuple

from app.config import settings


# ── Engine ────────────────────────────────────────────────────────────────────
is_sqlite = settings.DATABASE_URL.startswith("sqlite")
if is_sqlite:
    sqlite_path = make_url(settings.DATABASE_URL).database
    if sqlite_path and sqlite_path != ":memory:":
        Path(sqlite_path).parent.mkdir(parents=True, exist_ok=True)

engine_options = {
    "echo": settings.DEBUG,
}
if is_sqlite:
    engine_options["connect_args"] = {"check_same_thread": False}
else:
    engine_options.update({
        "pool_pre_ping": True,
        "pool_size": 1,
        "max_overflow": 0,
        "pool_recycle": 300,
    })

engine = create_engine(settings.DATABASE_URL, **engine_options)


if is_sqlite:
    @event.listens_for(engine, "connect")
    def enable_sqlite_foreign_keys(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


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
