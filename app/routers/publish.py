"""POST /<topic> — ntfy.sh-compatible publish endpoint.

Headers (case-insensitive, ntfy conventions):
  Authorization: Bearer tk_<base64>          — or session cookie
  Title:           <string>                  — message title
  Priority:        1..5                      — default = topic.default_priority
  Tags:            rotating_light,deploy     — CSV → list
  Click:           <url>                     — link target
  Icon:            <url>                     — icon URL
  Actions:         <json-string>             — JSON-encoded list of action dicts
  Id:              <external_id>             — idempotency key (returns 200 on collision)
  Content-Type:    text/plain | application/json

Auth: Bearer (HMAC-signed via X-Notifier-Signature) OR cookie session.
In both cases the resolved topic belongs to the authenticated user.

Body: raw bytes (the message body). Content-Type determines serialization.

Response: 201 on new message, 200 on idempotent re-publish (Id: collision).
"""
from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone

import orjson
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import get_current_user
from app.models import Topic, TopicKey, User
from app.secrets import SecretKeyError, decrypt_secret
from app.security import verify_bearer_topic_key
from app.services.messages import PublishResult, message_to_payload, publish_message

router = APIRouter(tags=["publish"])


# ntfy uses ±5 min timestamp window; we honour the same to prevent replay.
_MAX_TIMESTAMP_DRIFT_SECONDS = 300


def _parse_priority(raw: str | None) -> int | None:
    if raw is None:
        return None
    try:
        v = int(raw)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Priority header must be an integer 1..5",
        )
    if v < 1 or v > 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Priority header must be in 1..5",
        )
    return v


def _parse_actions(raw: str | None) -> list[dict] | None:
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Actions header must be valid JSON: {exc}",
        )
    if not isinstance(parsed, list):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Actions header must be a JSON array",
        )
    return parsed


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


async def _resolve_via_bearer(
    db: AsyncSession, request: Request
) -> tuple[Topic, User, str] | None:
    """Try to authenticate via Authorization: Bearer <token>.

    The token encodes the topic_key_id (uuid) + signature over (timestamp, body).
    Format: `<key_uuid>.<signature>` — keeps the wire format simple.
    Returns (topic, owner_user, scope) if auth succeeds; None if no Bearer header.
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
    key_id_str, signature = token.split(".", 1)
    try:
        key_id = uuid.UUID(key_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="malformed bearer token",
        )
    sig_header = request.headers.get("x-notifier-signature", "")
    ts_header = request.headers.get("x-notifier-timestamp", "")
    if not sig_header or not ts_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing X-Notifier-Signature or X-Notifier-Timestamp",
        )
    # Timestamp freshness check (replay protection).
    try:
        ts = int(ts_header)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="malformed X-Notifier-Timestamp",
        )
    now = int(time.time())
    if abs(now - ts) > _MAX_TIMESTAMP_DRIFT_SECONDS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Notifier-Timestamp out of window",
        )

    row = await db.execute(select(TopicKey).where(TopicKey.id == key_id))
    key = row.scalar_one_or_none()
    if key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="unknown bearer key"
        )

    body_bytes = await request.body()
    try:
        raw_secret = decrypt_secret(key.secret_ct)
    except SecretKeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        )
    if not verify_bearer_topic_key(raw_secret, body_bytes, sig_header, ts_header):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid signature"
        )

    # Resolve topic and owner.
    topic_row = await db.execute(select(Topic).where(Topic.id == key.topic_id))
    topic = topic_row.scalar_one_or_none()
    if topic is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="topic no longer exists"
        )
    owner = await db.get(User, topic.user_id)
    if owner is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="owner no longer exists"
        )
    # Bump last_used_at — best-effort.
    await db.execute(
        update(TopicKey).where(TopicKey.id == key.id).values(last_used_at=datetime.now(timezone.utc))
    )
    return topic, owner, key.scopes


async def _resolve_user_or_bearer(
    db: AsyncSession, request: Request
) -> tuple[Topic | None, User, str]:
    """Resolve (topic, user, scope). Tries Bearer first, falls back to cookie.

    `topic` is None when the auth method is cookie — we look it up by name from
    the URL path inside the handler. With Bearer, the topic is fixed by the key.
    """
    bearer = await _resolve_via_bearer(db, request)
    if bearer is not None:
        topic, user, scopes = bearer
        return topic, user, scopes

    # Cookie auth.
    user = await _get_user_or_401(db, request)
    return None, user, ""


async def _get_user_or_401(db: AsyncSession, request: Request) -> User:
    """Resolve the current user from cookie. 401 if missing/invalid."""
    from app.security import decode_session_jwt  # local import — avoid cycle

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
    return user


def _check_scope(scopes: str, needed: str) -> None:
    """403 if `needed` not in scopes CSV."""
    if not scopes or needed not in scopes.split(","):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"bearer key lacks '{needed}' scope",
        )


@router.post("/{topic}", status_code=status.HTTP_201_CREATED)
async def publish(
    topic: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Publish a message to <topic>. Returns 201 on insert, 200 on idempotent re-publish."""
    body_bytes = await request.body()
    if not body_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="empty body"
        )

    bearer_topic, user, scopes = await _resolve_user_or_bearer(db, request)
    if bearer_topic is not None:
        # Bearer auth — topic is fixed by the key. Reject mismatch.
        if bearer_topic.name != topic:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"bearer key is for topic '{bearer_topic.name}', not '{topic}'",
            )
        topic_obj = bearer_topic
        _check_scope(scopes, "publish")
    else:
        topic_obj = await _resolve_topic_for_user(db, user, topic)

    title = request.headers.get("title")
    priority = _parse_priority(request.headers.get("priority"))
    tags = request.headers.get("tags")
    click = request.headers.get("click")
    icon = request.headers.get("icon")
    actions = _parse_actions(request.headers.get("actions"))
    external_id = request.headers.get("id") or request.headers.get("x-id")
    content_type = (
        request.headers.get("content-type", "text/plain").split(";", 1)[0].strip()
        or "text/plain"
    )

    result = await publish_message(
        db,
        topic_obj,
        body=body_bytes,
        title=title,
        priority=priority,
        tags_csv=tags,
        click=click,
        icon=icon,
        actions=actions,
        external_id=external_id,
        content_type=content_type,
    )
    await db.commit()
    payload = message_to_payload(result.message, topic_name=topic_obj.name)
    out = orjson.dumps(payload)
    status_code = (
        status.HTTP_201_CREATED if result.created else status.HTTP_200_OK
    )
    return Response(
        content=out,
        media_type="application/json",
        status_code=status_code,
        headers={"Location": f"/{topic_obj.name}/json?since={result.message.time}"},
    )
