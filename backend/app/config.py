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

    # ── Database ──────────────────────────────────────────────────────────────
    DATABASE_URL: str  # required – no default

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


# Single, module-level instance – import this everywhere.
settings = Settings()
