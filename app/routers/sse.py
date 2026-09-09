"""SSE realtime stream + history endpoint — Phase 4.1.

GET /api/events/sse
    Auth required. Yields:
      - initial 'ready' event with user_id
      - 'notification' event (JSON, HistoryOut-shaped) for each v2 message
        published to any of the user's topics
      - 15s heartbeat so proxies don't idle us out
    On client disconnect: unsubscribe from all topic queues.

GET /api/events?since=<iso8601>&limit=50
    Auth required. Returns v2 messages from `messages` table joined with
    `topics` (filtered by current user_id), ordered by Message.time DESC.
    Payload shape is HistoryOut — keeps the SPA types stable (no web rebuild).

Phase 4.1 fix: this endpoint was previously wired to the LEGACY Phase 1
fanout (in_app_notifications + events + rules + per-user pubsub), which
never received v2 topic-anchored messages. After the Phase 4 SPA cutover
the dashboard showed empty + SSE Offline. This rewrite subscribes to the
v2 topic pubsub and reads from the `messages` table.

ponytail: payload mapping is intentionally lossy — v2 message fields
(`id`, `time`, `title`, `message`, `tags`, `click`) are projected into the
legacy HistoryOut shape so the SPA types don't have to change. Drop the
adapter when the SPA is upgraded to native v2 types (post-Phase 5).
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, AsyncIterator

import orjson
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import get_current_user
from app.models import Message, Topic, User
from app.schemas import parse_tags_csv
from app.services.pubsub_topics import TopicMessage, get_topic_pubsub

router = APIRouter(prefix="/api/events", tags=["events"])


# ── History ────────────────────────────────────────────────────────


class HistoryOut(BaseModel):
    """Legacy-shaped history row, kept stable for the SPA.

    `notification_id` and `event_id` are stable positive ints derived from
    the v2 message id (uuid4 hex) so React list keys remain stable across
    history reloads.
    """

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


def _stable_int_id(message_id: str) -> int:
    """Map a v2 message uuid4 hex to a stable positive 31-bit int.

    The first 8 hex chars (32 bits) ANDed with 0x7FFFFFFF keeps the result
    positive (avoids PostgreSQL int4 sign quirks if we ever persist) and
    stable for the same input.
    """
    return int(message_id[:8], 16) & 0x7FFFFFFF


def _project_from_tags(tags: list[str]) -> str | None:
    """Return the first tag that is NOT a `thread-*` status tag."""
    for t in tags:
        if not t.startswith("thread-"):
            return t
    return None


def _status_from_tags(tags: list[str]) -> str | None:
    for t in tags:
        if t.startswith("thread-"):
            return t.removeprefix("thread-")
    return None


def _message_to_history(msg: Message, topic_name: str) -> HistoryOut:
    tags = parse_tags_csv(msg.tags)
    ts = datetime.fromtimestamp(msg.time, tz=timezone.utc)
    body = msg.body or ""
    # First line of the body doubles as `summary` (matches the orchestrator's
    # `notify_v2.format_envelope()` which puts the meaningful sentence first
    # and structured metadata in subsequent lines).
    summary = body.split("\n", 1)[0].strip() or None
    return HistoryOut(
        notification_id=_stable_int_id(msg.id),
        event_id=_stable_int_id(msg.id),
        rule_id=None,  # v2 has no rules
        delivered_at=ts,
        event_name=msg.event,
        thread_id=None,  # not carried in v2 message; orchestrator embeds in body
        project_name=_project_from_tags(tags) or topic_name,
        summary=summary,
        status=_status_from_tags(tags),
        pr_url=msg.click,  # orchestrator sets click=pr_url
        occurred_at=ts,
        rule_name=None,
    )


@router.get("", response_model=list[HistoryOut])
async def history(
    since: str | None = Query(
        default=None,
        description="ISO-8601 timestamp; only messages at or after this are returned",
    ),
    limit: int = Query(default=50, ge=1, le=500),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[HistoryOut]:
    since_dt = _parse_since(since)
    since_epoch: int | None = int(since_dt.timestamp()) if since_dt else None

    # v2 messages joined with the user's topics. Single SQL roundtrip.
    stmt = (
        select(Message, Topic.name)
        .join(Topic, Message.topic_id == Topic.id)
        .where(Topic.user_id == user.id)
        .order_by(Message.time.desc())
        .limit(limit)
    )
    if since_epoch is not None:
        stmt = stmt.where(Message.time > since_epoch)

    rows = await db.execute(stmt)
    return [
        _message_to_history(msg, topic_name)
        for msg, topic_name in rows.all()
    ]


# ── Live SSE ───────────────────────────────────────────────────────


def _payload_to_notification_dict(payload: dict[str, Any]) -> dict:
    """Project a v2 message payload (ntfy wire format) into HistoryOut shape.

    Same fields as `_message_to_history` but for live SSE events where the
    full Message row isn't available — only the already-serialized payload
    that publish.py / pubsub_topics put on the wire.
    """
    tags = payload.get("tags") or []
    if isinstance(tags, str):
        tags = parse_tags_csv(tags)
    ts_epoch = int(payload.get("time") or 0)
    ts = datetime.fromtimestamp(ts_epoch, tz=timezone.utc) if ts_epoch else datetime.now(timezone.utc)
    body = payload.get("message") or ""
    summary = body.split("\n", 1)[0].strip() or None
    msg_id = str(payload.get("id") or "")
    notif_id = _stable_int_id(msg_id) if msg_id else 0
    return {
        "notification_id": notif_id,
        "event_id": notif_id,
        "rule_id": None,
        "delivered_at": ts.isoformat(),
        "event": payload.get("event") or "message",
        "thread_id": None,
        "project_name": _project_from_tags(tags) or payload.get("topic"),
        "summary": summary,
        "status": _status_from_tags(tags),
        "pr_url": payload.get("click"),
        "occurred_at": ts.isoformat(),
    }


async def _event_stream(
    user: User, db: AsyncSession
) -> AsyncIterator[dict]:
    yield {
        "event": "ready",
        "data": orjson.dumps({"user_id": str(user.id)}).decode(),
    }

    # Subscribe to every topic this user owns. A single merged queue keeps
    # the consumer code simple; forwarder tasks drain per-topic queues into
    # the merge and get cancelled on disconnect.
    topic_rows = await db.execute(select(Topic).where(Topic.user_id == user.id))
    topics = list(topic_rows.scalars().all())

    pubsub = get_topic_pubsub()
    merged: asyncio.Queue[TopicMessage | None] = asyncio.Queue()
    subscriptions: list[tuple[Any, Any]] = []
    forwarders: list[asyncio.Task[None]] = []

    for t in topics:
        sub_id, q = await pubsub.subscribe(t.id)
        subscriptions.append((t.id, sub_id))

        async def forward(_q: asyncio.Queue = q) -> None:
            try:
                while True:
                    tm = await _q.get()
                    await merged.put(tm)
            except asyncio.CancelledError:
                return

        forwarders.append(asyncio.create_task(forward()))

    try:
        while True:
            try:
                tm = await asyncio.wait_for(merged.get(), timeout=15.0)
            except asyncio.TimeoutError:
                yield {"event": "ping", "data": ""}
                continue
            yield {
                "event": "notification",
                "data": orjson.dumps(_payload_to_notification_dict(tm.payload)).decode(),
            }
    finally:
        for fwd in forwarders:
            fwd.cancel()
        for topic_id, sub_id in subscriptions:
            await pubsub.unsubscribe(topic_id, sub_id)


@router.get("/sse")
async def sse(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EventSourceResponse:
    return EventSourceResponse(
        _event_stream(user, db),
        ping=15,
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
