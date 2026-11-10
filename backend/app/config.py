"""
app/config.py
─────────────
Centralised application configuration loaded exclusively from environment
variables (or a .env file at the backend root).  No secrets are hard-coded.
"""
from __future__ import annotations

from pydantic import PositiveInt
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All tuneable knobs for SpendSense backend.

    Every field maps 1-to-1 to an environment variable (case-insensitive).
    Missing required fields raise a clear ValidationError at startup rather
    than a cryptic KeyError deep in business logic.
    """

    # ── Application ───────────────────────────────────────────────────────────
    APP_NAME: str = "SpendSense"
    DEBUG: bool = False
    ALLOWED_ORIGINS: str = (
        "http://127.0.0.1:5173,http://localhost:5173,"
        "https://se-max-submission.vercel.app"
    )

    # ── Database ──────────────────────────────────────────────────────────────
    # SQLite keeps local development self-contained. Set DATABASE_URL to a
    # PostgreSQL URL when deploying or running the PostgreSQL integration suite.
    DATABASE_URL: str = "sqlite:///./.sandbox/spendsense.db"

    # ── JWT ───────────────────────────────────────────────────────────────────
    SECRET_KEY: str          # required – no default
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # ── Timezone ──────────────────────────────────────────────────────────────
    LOCAL_TIMEZONE: str = "Asia/Karachi"

    # ── Gemini AI ─────────────────────────────────────────────────────────────
    GEMINI_API_KEY: str | None = None
    GEMINI_MODEL: str = "gemini-3.8-flash"
    GEMINI_TIMEOUT_SECONDS: PositiveInt = 15

    model_config = SettingsConfigDict(
        # Look for .env relative to the backend/ directory
        env_file=".env",
        env_file_encoding="utf-8",
        # Silently ignore extra env vars that don't map to a field
        extra="ignore",
    )

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]


# Single, module-level instance – import this everywhere.
settings = Settings()
