"""
Centralized configuration for TitanSwarm.

All runtime settings are read once from environment variables (or .env) and
validated at startup via Pydantic Settings.  Every module imports from here
instead of calling ``os.getenv()`` directly.

Usage::

    from src.core.config import settings
    dsn = settings.database_url
"""
from __future__ import annotations

import os
from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Typed, validated application settings.

    Values come from environment variables (case-insensitive) or a ``.env``
    file located two directories above this module (project root).
    """

    # ── AI Provider ──────────────────────────────────────────────────────────
    ai_provider: str = Field(
        default="gemini",
        description="LLM backend: 'gemini' or 'openai'.",
    )
    gemini_api_key: str = Field(
        default="",
        description="Google Gemini API key.",
    )
    openai_api_key: str = Field(
        default="",
        description="OpenAI API key (only needed if ai_provider=openai).",
    )

    # ── Database ─────────────────────────────────────────────────────────────
    database_url: str = Field(
        default="sqlite+aiosqlite:///titanswarm.db",
        description="Async SQLAlchemy connection string.",
    )

    # ── Scraper ──────────────────────────────────────────────────────────────
    scraper_roles: str = Field(
        default="Software Engineer Intern",
        description="Pipe-separated target job titles for the daemon.",
    )
    scraper_locations: str = Field(
        default="Vancouver, BC",
        description="Pipe-separated target locations for the daemon.",
    )
    scraper_interval_hours: int = Field(
        default=12, ge=1, le=168,
        description="Hours between background scrape cycles.",
    )
    scraper_results_wanted: int = Field(
        default=25, ge=5, le=200,
        description="Jobs fetched per role/location per sweep.",
    )

    # ── Session Security ─────────────────────────────────────────────────────
    session_secret: str = Field(
        default="",
        description="HMAC secret for signing session cookies.  "
                    "If empty, a random per-process secret is generated.",
    )

    # ── LinkedIn (optional) ──────────────────────────────────────────────────
    linkedin_login_email: str = ""
    linkedin_login_pass: str = ""
    linkedin_li_at: str = ""
    linkedin_jsessionid: str = ""

    model_config = {
        "env_file": os.path.join(
            os.path.dirname(__file__), "..", "..", ".env",
        ),
        "env_file_encoding": "utf-8",
        "extra": "ignore",          # don't crash on unknown env vars
        "case_sensitive": False,     # DATABASE_URL == database_url
    }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a singleton Settings instance (cached after first call)."""
    return Settings()


# Convenience alias — most callers just ``from src.core.config import settings``
settings = get_settings()
