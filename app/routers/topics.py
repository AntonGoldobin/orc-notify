"""Topic CRUD (cookie-authenticated, per-user scope).

Endpoints:
  GET    /api/topics            list current user's topics
  POST   /api/topics            create topic (UNIQUE per user_id+name)
  GET    /api/topics/{name}     fetch one topic
  PATCH  /api/topics/{name}     partial update (description / default_priority / retention_days / sound_id)
  DELETE /api/topics/{name}     cascade-deletes keys + messages

Per-user scope: `<name>` is unique within the user's namespace. Different
users may have the same topic name without collision.

Phase 2: accepts an optional `sound_id` on POST and PATCH. Sound must
belong to the requesting user; mismatched/foreign sound → 404 (trust
boundary — never 403, match the existing convention).
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_db
from app.deps import get_current_user
from app.models import Sound, Topic, User
from app.schemas import SoundOut, TopicIn, TopicOut, TopicPatch

router = APIRouter(prefix="/api/topics", tags=["topics"])


def _to_out(t: Topic) -> TopicOut:
    """Build TopicOut from the ORM row. `t.sound` must already be loaded
    (via selectinload in the query) — accessing it on an async session
    without eager loading raises MissingGreenlet.
    """
    if t.sound is not None:
        s = t.sound
        sound = SoundOut(
            id=str(s.id), name=s.name, url=s.url, created_at=s.created_at
        )
    else:
        sound = None
    return TopicOut(
        id=str(t.id),
        name=t.name,
        description=t.description,
        default_priority=t.default_priority,
        retention_days=t.retention_days,
        created_at=t.created_at,
        updated_at=t.updated_at,
        sound=sound,
    )


async def _resolve_sound_for_user(
    db: AsyncSession, user: User, sound_id_str: str
) -> Sound:
    """Validate the sound belongs to the requesting user. Foreign/missing → 404.

    Sound IDs in API are strings; we accept either a valid UUID or fail 404.
    """
    try:
        sid = uuid.UUID(sound_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Sound not found"
        )
    row = await db.execute(
        select(Sound).where(Sound.id == sid, Sound.user_id == user.id)
    )
    sound = row.scalar_one_or_none()
    if sound is None:
        # Foreign or unknown — both surface as 404 (no info leak about
        # whether the sound exists for some other user).
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Sound not found"
        )
    return sound


async def _load_by_name(
    db: AsyncSession, user: User, name: str
) -> Topic:
    row = await db.execute(
        select(Topic)
        .where(Topic.user_id == user.id, Topic.name == name)
        .options(selectinload(Topic.sound))
    )
    t = row.scalar_one_or_none()
    if t is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found"
        )
    return t


@router.get("", response_model=list[TopicOut])
async def list_topics(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[TopicOut]:
    rows = await db.execute(
        select(Topic)
        .where(Topic.user_id == user.id)
        .options(selectinload(Topic.sound))
        .order_by(Topic.created_at.desc())
    )
    return [_to_out(t) for t in rows.scalars().all()]


@router.post("", response_model=TopicOut, status_code=status.HTTP_201_CREATED)
async def create_topic(
    body: TopicIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TopicOut:
    sound_id_uuid: uuid.UUID | None = None
    if body.sound_id is not None:
        sound = await _resolve_sound_for_user(db, user, body.sound_id)
        sound_id_uuid = sound.id

    topic = Topic(
        user_id=user.id,
        name=body.name,
        description=body.description,
        default_priority=body.default_priority if body.default_priority is not None else 3,
        retention_days=body.retention_days if body.retention_days is not None else 7,
        sound_id=sound_id_uuid,
    )
    db.add(topic)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"topic '{body.name}' already exists",
        )
    await db.refresh(topic)
    # After refresh, the sound relationship is loaded lazily on access —
    # but on async sessions that triggers IO inside the response path. Re-load
    # with selectinload so `_to_out` doesn't trip MissingGreenlet.
    row = await db.execute(
        select(Topic).where(Topic.id == topic.id).options(selectinload(Topic.sound))
    )
    return _to_out(row.scalar_one())


@router.get("/{name}", response_model=TopicOut)
async def get_topic(
    name: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TopicOut:
    return _to_out(await _load_by_name(db, user, name))


@router.patch("/{name}", response_model=TopicOut)
async def patch_topic(
    name: str,
    body: TopicPatch,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TopicOut:
    topic = await _load_by_name(db, user, name)
    if body.description is not None:
        topic.description = body.description
    if body.default_priority is not None:
        topic.default_priority = body.default_priority
    if body.retention_days is not None:
        topic.retention_days = body.retention_days
    # sound_id: distinguish "field absent" (no change) from "explicit null"
    # (detach) via Pydantic's `model_fields_set`. Without this, the user can
    # never unset a sound via PATCH.
    if "sound_id" in body.model_fields_set:
        if body.sound_id is None:
            topic.sound_id = None
        else:
            sound = await _resolve_sound_for_user(db, user, body.sound_id)
            topic.sound_id = sound.id
    await db.commit()
    await db.refresh(topic)
    row = await db.execute(
        select(Topic).where(Topic.id == topic.id).options(selectinload(Topic.sound))
    )
    return _to_out(row.scalar_one())


@router.delete("/{name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_topic(
    name: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    topic = await _load_by_name(db, user, name)
    await db.delete(topic)
    await db.commit()
