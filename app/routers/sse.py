"""SSE realtime stream + history endpoint.

GET /api/events/sse
    Auth required. Yields:
      - initial 'ready' event with user_id
      - 'notification' event (JSON) for each queued Notification
      - 15s heartbeat so proxies don't idle us out
    On client disconnect: unsubscribe from pubsub.

GET /api/events?since=<iso8601>&limit=50
    Auth required. Returns rows from in_app_notifications JOIN events JOIN rules
    for the current user, ordered by delivered_at DESC.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import AsyncIterator

import orjson
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import get_current_user
from app.models import User
from app.services.events import get_user_notifications
from app.services.pubsub import Notification, get_pubsub

router = APIRouter(prefix="/api/events", tags=["events"])


# ── History ────────────────────────────────────────────────────────


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


def _parse_since(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


@router.get("", response_model=list[HistoryOut])
async def history(
    since: str | None = Query(
        default=None,
        description="ISO-8601 timestamp; only notifications at or after this are returned",
    ),
    limit: int = Query(default=50, ge=1, le=500),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[HistoryOut]:
    since_dt = _parse_since(since)
    rows = await get_user_notifications(db, user.id, since=since_dt, limit=limit)
    out: list[HistoryOut] = []
    for n, e, r in rows:
        out.append(
            HistoryOut(
                notification_id=n.id,
                event_id=e.id,
                rule_id=str(n.rule_id) if n.rule_id else None,
                delivered_at=n.delivered_at,
                event_name=e.event,
                thread_id=e.thread_id,
                project_name=e.project_name,
                summary=e.summary,
                status=e.status,
                pr_url=e.pr_url,
                occurred_at=e.occurred_at,
                rule_name=r.name if r else None,
            )
        )
    return out


# ── Live SSE ───────────────────────────────────────────────────────


def _notification_to_dict(n: Notification) -> dict:
    return {
        "notification_id": n.notification_id,
        "event_id": n.event_id,
        "rule_id": str(n.rule_id) if n.rule_id else None,
        "delivered_at": n.delivered_at.isoformat(),
        "event": n.event_name,
        "thread_id": n.thread_id,
        "project_name": n.project_name,
        "summary": n.summary,
        "status": n.status,
        "pr_url": n.pr_url,
        "occurred_at": n.occurred_at.isoformat() if n.occurred_at else None,
    }


async def _event_stream(
    user_id: uuid.UUID, queue: asyncio.Queue[Notification]
) -> AsyncIterator[dict]:
    yield {
        "event": "ready",
        "data": orjson.dumps({"user_id": str(user_id)}).decode(),
    }
    try:
        while True:
            try:
                notif = await asyncio.wait_for(queue.get(), timeout=15.0)
            except asyncio.TimeoutError:
                yield {"event": "ping", "data": ""}
                continue
            yield {
                "event": "notification",
                "data": orjson.dumps(_notification_to_dict(notif)).decode(),
            }
    finally:
        await get_pubsub().unsubscribe(user_id, queue)


@router.get("/sse")
async def sse(
    user: User = Depends(get_current_user),
) -> EventSourceResponse:
    queue = await get_pubsub().subscribe(user.id)
    return EventSourceResponse(
        _event_stream(user.id, queue),
        ping=15,
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )