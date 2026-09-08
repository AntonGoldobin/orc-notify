"""Pydantic schemas shared across routers.

Single source of truth for UserOut / AgentOut / Topic / TopicKey / Message
shapes. Routers import from here; duplicate definitions in routers/auth.py
and routers/api_keys.py were removed in Phase 1.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ── Users ──────────────────────────────────────────────────────────


class UserOut(BaseModel):
    id: str
    email: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Rules (legacy; Phase 5 removes) ────────────────────────────────


class RuleIn(BaseModel):
    """POST /api/rules request body. PUT /api/rules/{id} accepts a subset."""

    name: str = Field(min_length=1, max_length=120)
    event_pattern: str = Field(min_length=1, max_length=255)
    channel: str = "sse"
    enabled: bool = True


class RulePatch(BaseModel):
    """PUT /api/rules/{id} — partial update. All fields optional."""

    name: str | None = Field(default=None, min_length=1, max_length=120)
    event_pattern: str | None = Field(default=None, min_length=1, max_length=255)
    channel: str | None = None
    enabled: bool | None = None


class RuleOut(BaseModel):
    id: str
    name: str
    event_pattern: str
    channel: str
    enabled: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Agents / API keys (legacy; superseded by topic_keys) ───────────


class AgentOut(BaseModel):
    id: str
    agent_id: str
    name: str
    created_at: datetime
    last_event_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class AgentCreatedOut(AgentOut):
    """Returned exactly once on create / rotate — includes the raw webhook_secret."""

    webhook_secret: str | None = None


# ── History (legacy per-user fanout) ───────────────────────────────


class HistoryOut(BaseModel):
    notification_id: int
    event_id: int
    rule_id: str | None
    delivered_at: datetime
    event_name: str
    thread_id: str | None
    project_name: str | None
    summary: str | None
    status: str | None
    pr_url: str | None
    occurred_at: datetime | None
    rule_name: str | None


# ── Topics (Phase 1) ──────────────────────────────────────────────


class TopicIn(BaseModel):
    """POST /api/topics body."""

    name: str = Field(
        min_length=1,
        max_length=120,
        pattern=r"^[A-Za-z0-9_\-]+$",
        description="URL-safe topic name; letters/digits/underscore/dash only.",
    )
    description: str | None = Field(default=None, max_length=500)
    default_priority: int | None = Field(default=None, ge=1, le=5)
    retention_days: int | None = Field(default=None, ge=1, le=365)


class TopicPatch(BaseModel):
    """PATCH /api/topics/{name} — partial update."""

    description: str | None = Field(default=None, max_length=500)
    default_priority: int | None = Field(default=None, ge=1, le=5)
    retention_days: int | None = Field(default=None, ge=1, le=365)


class TopicOut(BaseModel):
    id: str
    name: str
    description: str | None
    default_priority: int
    retention_days: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Topic keys (Phase 1) ──────────────────────────────────────────


class TopicKeyIn(BaseModel):
    """POST /api/topics/{name}/keys body."""

    name: str = Field(min_length=1, max_length=120)
    scopes: str = Field(
        default="publish,read",
        description="CSV subset of 'publish,read'.",
    )


class TopicKeyPatch(BaseModel):
    """PATCH /api/topics/{name}/keys/{id} — rotate or rename."""

    name: str | None = Field(default=None, min_length=1, max_length=120)
    scopes: str | None = None


class TopicKeyOut(BaseModel):
    id: str
    topic_id: str
    name: str
    scopes: str
    created_at: datetime
    last_used_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class TopicKeyCreatedOut(TopicKeyOut):
    """Returned exactly once on create / rotate — includes the raw secret."""

    secret: str | None = None


# ── Messages (Phase 1) ─────────────────────────────────────────────


class MessageOut(BaseModel):
    """ntfy.sh-compatible message envelope."""

    id: str
    time: int
    event: str
    topic: str
    title: str | None
    message: str
    priority: int
    tags: list[str]
    click: str | None
    icon: str | None
    actions: list[dict] | None
    content_type: str

    model_config = ConfigDict(from_attributes=True)


def parse_tags_csv(raw: str | None) -> list[str]:
    """CSV string → list of trimmed, non-empty tags. Empty in → empty out."""
    if not raw:
        return []
    return [t.strip() for t in raw.split(",") if t.strip()]


def format_tags_csv(tags: list[str] | None) -> str | None:
    """List → CSV. None / empty in → None out (NULL in DB)."""
    if not tags:
        return None
    cleaned = [t.strip() for t in tags if t and t.strip()]
    return ",".join(cleaned) if cleaned else None
