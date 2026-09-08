"""Topic subscribe endpoints — GET /<topic>/{json,sse,raw,auth}.

All read endpoints require either a cookie session OR a topic key with `read`
scope. ntfy.sh URL contract mirrored verbatim.

  GET /<topic>/json            poll messages since ?since=<epoch>
  GET /<topic>/sse             long-lived SSE stream
  GET /<topic>/raw             line-delimited text body
  GET /<topic>/auth            200 if the caller can read

Note: /<topic>/ws (WebSocket) is out of scope for Phase 1.
"""
from __future__ import annotations

import asyncio
import uuid
from typing import AsyncIterator

import orjson
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Message, Topic, TopicKey, User
from app.security import decode_session_jwt
from app.services.messages import message_to_payload
from app.services.pubsub_topics import TopicMessage, get_topic_pubsub

router = APIRouter(tags=["subscribe"])


async def _resolve_topic_for_user(
    db: AsyncSession, user: User, name: str
) -> Topic:
    row = await db.execute(
        select(Topic).where(Topic.user_id == user.id, Topic.name == name)
    )
    t = row.scalar_one_or_none()
    if t is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"unknown topic '{name}'"
        )
    return t


async def _resolve_bearer_topic(
    db: AsyncSession, request: Request
) -> tuple[Topic, str] | None:
    """Return (Topic, scopes_csv) when Authorization: Bearer is present.

    Read endpoints only need the key id (HMAC is for write). We check the
    'read' scope and resolve the topic the key belongs to. Returns None when
    no Bearer header (caller falls back to cookie auth).
    """
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        return None
    token = auth[7:].strip()
    if "." not in token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="malformed bearer token",
        )
    key_id_str = token.split(".", 1)[0]
    try:
        key_id = uuid.UUID(key_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="malformed bearer token",
        )
    row = await db.execute(select(TopicKey).where(TopicKey.id == key_id))
    key = row.scalar_one_or_none()
    if key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="unknown bearer key"
        )
    if "read" not in key.scopes.split(","):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="bearer key lacks 'read' scope",
        )
    topic_row = await db.execute(select(Topic).where(Topic.id == key.topic_id))
    topic = topic_row.scalar_one_or_none()
    if topic is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="topic no longer exists"
        )
    return topic, key.scopes


async def _resolve_reader(
    db: AsyncSession, request: Request, topic_name: str
) -> tuple[Topic, str]:
    """Resolve (topic, scopes_csv) for read access.

    Cookie auth: <topic_name> resolves as (user, name).
    Bearer auth: scope must include 'read'.
    Raises 401 / 403 on failure.
    """
    bearer = await _resolve_bearer_topic(db, request)
    if bearer is not None:
        bearer_topic, scopes = bearer
        if bearer_topic.name != topic_name:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"bearer key is for topic '{bearer_topic.name}', not '{topic_name}'",
            )
        return bearer_topic, scopes

    # Cookie auth fallback.
    cookie = request.cookies.get("notifier_session")
    if not cookie:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="authentication required",
        )
    user_id = decode_session_jwt(cookie)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or expired session",
        )
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="user no longer exists",
        )
    topic = await _resolve_topic_for_user(db, user, topic_name)
    return topic, ""


# ── /<topic>/json — poll ───────────────────────────────────────────


@router.get("/{topic}/json")
async def poll_json(
    topic: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    since: int | None = Query(default=None, ge=0),
) -> Response:
    topic_obj, _scopes = await _resolve_reader(db, request, topic)
    q = select(Message).where(Message.topic_id == topic_obj.id)
    if since is not None:
        q = q.where(Message.time > since)
    q = q.order_by(Message.time.asc()).limit(200)
    rows = await db.execute(q)
    msgs = [message_to_payload(m, topic_name=topic_obj.name) for m in rows.scalars().all()]
    return Response(
        content=orjson.dumps(msgs),
        media_type="application/x-ndjson",
        status_code=status.HTTP_200_OK,
    )


# ── /<topic>/sse — long-lived stream ──────────────────────────────


async def _sse_stream(
    topic_obj: Topic, sub_id: uuid.UUID, queue: asyncio.Queue[TopicMessage]
) -> AsyncIterator[dict]:
    try:
        # Initial ready event.
        yield {
            "event": "ready",
            "data": orjson.dumps({"topic": topic_obj.name}).decode(),
        }
        while True:
            try:
                msg = await asyncio.wait_for(queue.get(), timeout=15.0)
            except asyncio.TimeoutError:
                yield {"event": "ping", "data": ""}
                continue
            yield {"event": "message", "data": orjson.dumps(msg.payload).decode()}
    finally:
        await get_topic_pubsub().unsubscribe(topic_obj.id, sub_id)


@router.get("/{topic}/sse")
async def subscribe_sse(
    topic: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> EventSourceResponse:
    topic_obj, _scopes = await _resolve_reader(db, request, topic)
    sub_id, queue = await get_topic_pubsub().subscribe(topic_obj.id)
    return EventSourceResponse(
        _sse_stream(topic_obj, sub_id, queue),
        ping=15,
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ── /<topic>/raw — line-delimited text body ───────────────────────


@router.get("/{topic}/raw")
async def poll_raw(
    topic: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    since: int | None = Query(default=None, ge=0),
) -> StreamingResponse:
    topic_obj, _scopes = await _resolve_reader(db, request, topic)
    q = select(Message).where(Message.topic_id == topic_obj.id)
    if since is not None:
        q = q.where(Message.time > since)
    q = q.order_by(Message.time.asc()).limit(200)
    rows = await db.execute(q)

    async def _gen() -> AsyncIterator[bytes]:
        for m in rows.scalars().all():
            payload = message_to_payload(m, topic_name=topic_obj.name)
            # ntfy.sh raw format: one JSON object per line.
            yield orjson.dumps(payload) + b"\n"

    return StreamingResponse(_gen(), media_type="application/x-ndjson")


# ── /<topic>/auth — capability probe ──────────────────────────────


@router.get("/{topic}/auth")
async def auth_probe(
    topic: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """200 if the caller can read this topic. Used by ntfy clients for
    capability check before subscribing.
    """
    topic_obj, _scopes = await _resolve_reader(db, request, topic)
    return {
        "topic": topic_obj.name,
        "id": str(topic_obj.id),
        "can_read": True,
    }
