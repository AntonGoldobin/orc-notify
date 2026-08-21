"""API key (agent) management + public agent health endpoint.

Endpoints (all auth-guarded except /v1/agents/{agent_id}/health):
  - GET    /api/keys                          list current user's agents
  - POST   /api/keys                          create agent, returns secret ONCE
  - DELETE /api/keys/{agent_id}               delete agent; events.agent_id → SET NULL
  - POST   /api/keys/{agent_id}/rotate-secret new secret, returned ONCE
  - GET    /v1/agents/{agent_id}/health       public liveness probe (no auth)

The webhook_secret is Fernet-encrypted at rest (app.secrets). When returning
agents to the user, we expose every field EXCEPT the secret — except on create
and rotate, where the raw secret is returned exactly once.
"""
from __future__ import annotations

import secrets
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import get_current_user
from app.models import Agent, User
from app.secrets import SecretKeyError, encrypt_secret

router = APIRouter(tags=["api-keys"])


# ── Schemas ────────────────────────────────────────────────────────


class AgentOut(BaseModel):
    id: str
    agent_id: str
    name: str
    created_at: datetime
    last_event_at: datetime | None

    @classmethod
    def from_agent(cls, a: Agent) -> "AgentOut":
        return cls(
            id=str(a.id),
            agent_id=a.agent_id,
            name=a.name,
            created_at=a.created_at,
            last_event_at=a.last_event_at,
        )


class AgentCreatedOut(AgentOut):
    """Returned exactly once on create/rotate — includes the raw webhook_secret."""

    webhook_secret: str | None = None  # set by endpoint after from_agent()


class AgentCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    agent_id: str | None = Field(
        default=None,
        max_length=255,
        description="Optional. Auto-generated as '<slug>-<rand6>' if omitted.",
    )


class HealthOut(BaseModel):
    agent_id: str
    last_event_at: datetime | None
    status: str  # "ok" (recent activity) | "idle" | "unknown"


# ── Helpers ────────────────────────────────────────────────────────


def _slug(s: str) -> str:
    """Lowercase, replace non-alnum with '-', collapse, strip edges."""
    out = []
    for ch in s.lower():
        out.append(ch if ch.isalnum() else "-")
    slug = "".join(out)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-") or "agent"


async def _unique_agent_id(db: AsyncSession, requested: str | None, name: str) -> str:
    """Resolve the agent_id to use. If user supplied an explicit agent_id
    that collides, raise 409 — they asked for that exact value.
    If user did NOT supply one, auto-generate from name + random suffix.
    """
    if requested is not None:
        # Explicit: honor the user's choice, reject on collision.
        exists = await db.execute(
            select(Agent.id).where(Agent.agent_id == requested).limit(1)
        )
        if exists.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"agent_id '{requested}' is taken; please pick a different one",
            )
        return requested
    # Auto: keep retrying with fresh random suffix until unique.
    base = f"{_slug(name)}-{secrets.token_hex(3)}"
    for _ in range(5):
        exists = await db.execute(
            select(Agent.id).where(Agent.agent_id == base).limit(1)
        )
        if exists.scalar_one_or_none() is None:
            return base
        base = f"{_slug(name)}-{secrets.token_hex(3)}"
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="could not auto-generate a unique agent_id after 5 attempts",
    )


async def _get_user_agent(db: AsyncSession, user: User, agent_id: str) -> Agent:
    agent = await db.execute(
        select(Agent).where(Agent.user_id == user.id, Agent.agent_id == agent_id)
    )
    a = agent.scalar_one_or_none()
    if a is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found"
        )
    return a


# ── Endpoints ──────────────────────────────────────────────────────


@router.get("/api/keys", response_model=list[AgentOut])
async def list_agents(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[AgentOut]:
    rows = await db.execute(
        select(Agent)
        .where(Agent.user_id == user.id)
        .order_by(Agent.created_at.desc())
    )
    return [AgentOut.from_agent(a) for a in rows.scalars().all()]


@router.post(
    "/api/keys",
    response_model=AgentCreatedOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_agent(
    body: AgentCreateIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AgentCreatedOut:
    raw_secret = secrets.token_urlsafe(32)
    try:
        encrypted = encrypt_secret(raw_secret)
    except SecretKeyError as exc:
        # 503 — server misconfigured; client can't fix it.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        )
    chosen_agent_id = await _unique_agent_id(db, body.agent_id, body.name)
    agent = Agent(
        user_id=user.id,
        name=body.name,
        agent_id=chosen_agent_id,
        webhook_secret_ct=encrypted,
    )
    db.add(agent)
    try:
        await db.commit()
    except IntegrityError:
        # Race: someone created the same agent_id between our check and INSERT.
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"agent_id '{chosen_agent_id}' is taken; please retry",
        )
    await db.refresh(agent)
    out = AgentCreatedOut.from_agent(agent)
    out.webhook_secret = raw_secret
    return out


@router.delete("/api/keys/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    agent = await _get_user_agent(db, user, agent_id)
    await db.delete(agent)
    await db.commit()


@router.post(
    "/api/keys/{agent_id}/rotate-secret",
    response_model=AgentCreatedOut,
)
async def rotate_secret(
    agent_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AgentCreatedOut:
    agent = await _get_user_agent(db, user, agent_id)
    raw_secret = secrets.token_urlsafe(32)
    try:
        agent.webhook_secret_ct = encrypt_secret(raw_secret)
    except SecretKeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        )
    await db.commit()
    await db.refresh(agent)
    out = AgentCreatedOut.from_agent(agent)
    out.webhook_secret = raw_secret
    return out


@router.get("/v1/agents/{agent_id}/health", response_model=HealthOut)
async def agent_health(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
) -> HealthOut:
    """Public liveness probe — orchestrator pings this to confirm reachability.

    No auth: by design, anyone with the agent_id can probe. The agent_id is
    not a secret (the secret is the HMAC key). Status is informational only.
    """
    row = await db.execute(
        select(Agent).where(Agent.agent_id == agent_id).limit(1)
    )
    agent = row.scalar_one_or_none()
    if agent is None:
        # 404 so orchestrator config errors surface fast, not silent idle.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Unknown agent_id"
        )
    return HealthOut(
        agent_id=agent.agent_id,
        last_event_at=agent.last_event_at,
        status="ok",
    )