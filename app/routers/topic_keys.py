"""Topic key CRUD (cookie-authenticated, per-topic scope).

Endpoints (all under /api/topics/{name}/keys):
  GET    /                       list keys for topic (no secret)
  POST   /                       create key; secret returned ONCE
  PATCH  /{key_id}               rename / rotate (returns fresh secret ONCE)
  DELETE /{key_id}               revoke (204)

Secret handling: raw HMAC secret is Fernet-encrypted at rest (mirror of agents).
On POST and PATCH-with-rotation we surface the plaintext to the caller — they
must store it. Subsequent GETs return only metadata (no secret).
"""
from __future__ import annotations

import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import get_current_user
from app.models import Topic, TopicKey, User
from app.schemas import TopicKeyCreatedOut, TopicKeyIn, TopicKeyOut, TopicKeyPatch
from app.secrets import SecretKeyError, encrypt_secret

router = APIRouter(prefix="/api/topics/{name}/keys", tags=["topic-keys"])


_VALID_SCOPES = {"publish", "read"}


def _normalize_scopes(raw: str) -> str:
    """Accept 'publish,read' or 'publish' — return canonical 'publish,read' CSV."""
    parts = [s.strip() for s in raw.split(",") if s.strip()]
    invalid = [s for s in parts if s not in _VALID_SCOPES]
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"unknown scope(s): {invalid}; valid: {sorted(_VALID_SCOPES)}",
        )
    if not parts:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="at least one scope required",
        )
    # Preserve stable order: publish first, read second.
    canonical = [s for s in ("publish", "read") if s in parts]
    return ",".join(canonical)


def _to_out(k: TopicKey) -> TopicKeyOut:
    return TopicKeyOut(
        id=str(k.id),
        topic_id=str(k.topic_id),
        name=k.name,
        scopes=k.scopes,
        created_at=k.created_at,
        last_used_at=k.last_used_at,
    )


def _to_created_out(k: TopicKey, secret: str) -> TopicKeyCreatedOut:
    return TopicKeyCreatedOut(
        id=str(k.id),
        topic_id=str(k.topic_id),
        name=k.name,
        scopes=k.scopes,
        created_at=k.created_at,
        last_used_at=k.last_used_at,
        secret=secret,
    )


async def _load_topic(db: AsyncSession, user: User, name: str) -> Topic:
    row = await db.execute(
        select(Topic).where(Topic.user_id == user.id, Topic.name == name)
    )
    t = row.scalar_one_or_none()
    if t is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found"
        )
    return t


async def _load_key(
    db: AsyncSession, topic: Topic, key_id: str
) -> TopicKey:
    try:
        kid = uuid.UUID(key_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Topic key not found"
        )
    row = await db.execute(
        select(TopicKey).where(TopicKey.id == kid, TopicKey.topic_id == topic.id)
    )
    k = row.scalar_one_or_none()
    if k is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Topic key not found"
        )
    return k


@router.get("", response_model=list[TopicKeyOut])
async def list_keys(
    name: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[TopicKeyOut]:
    topic = await _load_topic(db, user, name)
    rows = await db.execute(
        select(TopicKey)
        .where(TopicKey.topic_id == topic.id)
        .order_by(TopicKey.created_at.desc())
    )
    return [_to_out(k) for k in rows.scalars().all()]


@router.post(
    "",
    response_model=TopicKeyCreatedOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_key(
    name: str,
    body: TopicKeyIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TopicKeyCreatedOut:
    topic = await _load_topic(db, user, name)
    raw_secret = secrets.token_urlsafe(32)
    try:
        ct = encrypt_secret(raw_secret)
    except SecretKeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        )
    scopes = _normalize_scopes(body.scopes)
    key = TopicKey(topic_id=topic.id, name=body.name, secret_ct=ct, scopes=scopes)
    db.add(key)
    await db.commit()
    await db.refresh(key)
    return _to_created_out(key, raw_secret)


@router.patch("/{key_id}", response_model=TopicKeyCreatedOut)
async def patch_key(
    name: str,
    key_id: str,
    body: TopicKeyPatch,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TopicKeyCreatedOut:
    """Rename, change scopes, or rotate secret.

    PATCH with `secret` in body would be ideal but we don't expose `secret` in
    TopicKeyPatch — rotation is implicit (always performed on PATCH for v1).
    """
    topic = await _load_topic(db, user, name)
    key = await _load_key(db, topic, key_id)
    if body.name is not None:
        key.name = body.name
    if body.scopes is not None:
        key.scopes = _normalize_scopes(body.scopes)
    # Always rotate secret on PATCH — simple, predictable, secure by default.
    raw_secret = secrets.token_urlsafe(32)
    try:
        key.secret_ct = encrypt_secret(raw_secret)
    except SecretKeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        )
    await db.commit()
    await db.refresh(key)
    return _to_created_out(key, raw_secret)


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_key(
    name: str,
    key_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    topic = await _load_topic(db, user, name)
    key = await _load_key(db, topic, key_id)
    await db.delete(key)
    await db.commit()
