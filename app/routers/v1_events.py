"""Agent webhook receiver (v1 API).

Headers required on every POST:
  X-Notifier-Agent:    <agent_id>          — identifies which user owns this event
  X-Notifier-Signature: <hex sha256 hmac>  — HMAC-SHA256(webhook_secret, raw_body)

On success:
  - Insert Event row
  - Fan out to matching rules (services.events.enqueue_event)
  - Publish to per-user SSE queue
  - Return 202 {event_id, matched_rule_count}

Failure modes:
  - 401 missing/wrong signature (constant-time compare via hmac.compare_digest)
  - 404 unknown agent_id
  - 422 missing required fields (event, thread_id, status)
"""
from __future__ import annotations

import hashlib
import hmac
from typing import Any

import orjson
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Agent
from app.secrets import SecretKeyError, decrypt_secret
from app.services.events import enqueue_event

router = APIRouter(prefix="/v1", tags=["v1"])


# ── Schemas ────────────────────────────────────────────────────────


class EventAccepted(BaseModel):
    event_id: int
    matched_rule_count: int = Field(ge=0)


# ── Helpers ────────────────────────────────────────────────────────


def _verify_signature(secret: str, body: bytes, signature_hex: str) -> bool:
    """Constant-time HMAC-SHA256 verify. Returns False on any decoding error."""
    if not signature_hex:
        return False
    try:
        expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature_hex.lower())
    except (AttributeError, TypeError):
        return False


def _validate_envelope(payload: Any) -> None:
    """422 if `event` is missing or non-string, or required orchestrator fields
    are absent. We validate here (not via Pydantic) because the body is raw
    bytes and we already parsed it with orjson for speed.
    """
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="body must be a JSON object",
        )
    event = payload.get("event")
    if not isinstance(event, str) or not event:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="missing required field 'event'",
        )
    # thread_id and status are required by orchestrator envelope contract.
    if "thread_id" not in payload:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="missing required field 'thread_id'",
        )
    if "status" not in payload:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="missing required field 'status'",
        )


# ── Endpoint ───────────────────────────────────────────────────────


@router.post(
    "/events",
    response_model=EventAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def post_event(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> EventAccepted:
    agent_id = request.headers.get("x-notifier-agent")
    if not agent_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing X-Notifier-Agent header",
        )
    signature = request.headers.get("x-notifier-signature", "")

    # Read raw bytes — HMAC must sign what the sender hashed, not re-serialized.
    body = await request.body()
    if not body:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="empty body",
        )

    agent = await db.get(Agent, None)  # no-op; we want select-by-agent_id
    agent = (
        await db.execute(  # type: ignore[assignment]
            Agent.__table__.select().where(Agent.agent_id == agent_id)
        )
    ).first()
    if agent is None:
        # No enumeration of agent_ids — but agent_id is not a secret.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"unknown agent_id '{agent_id}'",
        )
    # Re-fetch via ORM so we get the model instance, not a Row.
    agent = await db.get(Agent, agent.id)

    # Decrypt the secret to verify HMAC.
    try:
        raw_secret = decrypt_secret(agent.webhook_secret_ct)
    except SecretKeyError as exc:
        # Operator action required (rotate Fernet key + re-encrypt stored rows).
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        )

    if not _verify_signature(raw_secret, body, signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid signature",
        )

    try:
        payload = orjson.loads(body)
    except orjson.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"invalid JSON: {exc}",
        )
    _validate_envelope(payload)

    event, notifications = await enqueue_event(db, agent, payload)
    return EventAccepted(
        event_id=event.id,
        matched_rule_count=len(notifications),
    )