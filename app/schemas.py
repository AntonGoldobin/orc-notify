"""Pydantic schemas shared across routers.

Keeping these here lets N7 (rules CRUD) and N8 (UI) reuse the same shapes
without duplicating field definitions.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UserOut(BaseModel):
    id: str
    email: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


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


class AgentOut(BaseModel):
    id: str
    agent_id: str
    name: str
    created_at: datetime
    last_event_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class AgentCreatedOut(AgentOut):
    webhook_secret: str | None = None


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