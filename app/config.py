"""Settings for orc-notify.

Pydantic v2 with pydantic-settings. Reads from env vars (and .env file in dev).
Pattern mirrors `langgraph-cloud-agents/app/config.py` in the orchestrator repo.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Database ──────────────────────────────────────────────────
    database_url: str = Field(
        default="postgresql+asyncpg://notifier:notifier@localhost:5432/orc-notify",
        description="async Postgres URL (sqlalchemy+asyncpg format)",
    )

    # ── JWT ───────────────────────────────────────────────────────
    jwt_secret: str = Field(
        default="dev-only-change-me-in-production",
        description="HMAC secret for signing session cookies",
        min_length=16,
    )
    jwt_alg: Literal["HS256", "HS384", "HS512"] = "HS256"
    jwt_ttl_minutes: int = Field(default=43200, ge=60, le=525600)  # 30 days max

    # ── Cookie ────────────────────────────────────────────────────
    cookie_name: str = "notifier_session"
    cookie_secure: bool = True
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    # Cookie domain — set to ".orc.golden-antelope.ru" so a future sibling
    # sub-app on the same wildcard can share the session.
    cookie_domain: str | None = None

    # ── Public URL ────────────────────────────────────────────────
    # Used to build password reset links like https://{public_base_url}/reset?token=...
    public_base_url: str = "http://localhost:8000"

    # ── Webhook secret encryption ─────────────────────────────────
    # Fernet key (44-char urlsafe-base64-encoded 32-byte key) used to encrypt
    # agent webhook secrets at rest. Generate via:
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    # Rotate by setting both old + new and re-encrypting rows.
    webhook_secret_key: str = Field(
        default="",
        description="Fernet key for at-rest webhook secret encryption (44 chars)",
    )

    # ── App metadata ──────────────────────────────────────────────
    app_name: str = "orc-notify"
    log_level: str = "INFO"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
