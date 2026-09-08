"""Topic CRUD (cookie-authenticated, per-user scope).

Endpoints:
  GET    /api/topics            list current user's topics
  POST   /api/topics            create topic (UNIQUE per user_id+name)
  GET    /api/topics/{name}     fetch one topic
  PATCH  /api/topics/{name}     partial update (description / default_priority / retention_days)
  DELETE /api/topics/{name}     cascade-deletes keys + messages

Per-user scope: `<name>` is unique within the user's namespace. Different
users may have the same topic name without collision.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import get_current_user
from app.models import Topic, User
from app.schemas import TopicIn, TopicOut, TopicPatch

router = APIRouter(prefix="/api/topics", tags=["topics"])


def _to_out(t: Topic) -> TopicOut:
    return TopicOut(
        id=str(t.id),
        name=t.name,
        description=t.description,
        default_priority=t.default_priority,
        retention_days=t.retention_days,
        created_at=t.created_at,
        updated_at=t.updated_at,
    )


async def _load_by_name(
    db: AsyncSession, user: User, name: str
) -> Topic:
    row = await db.execute(
        select(Topic).where(Topic.user_id == user.id, Topic.name == name)
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
        .order_by(Topic.created_at.desc())
    )
    return [_to_out(t) for t in rows.scalars().all()]


@router.post("", response_model=TopicOut, status_code=status.HTTP_201_CREATED)
async def create_topic(
    body: TopicIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TopicOut:
    topic = Topic(
        user_id=user.id,
        name=body.name,
        description=body.description,
        default_priority=body.default_priority if body.default_priority is not None else 3,
        retention_days=body.retention_days if body.retention_days is not None else 7,
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
    return _to_out(topic)


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
    await db.commit()
    await db.refresh(topic)
    return _to_out(topic)


@router.delete("/{name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_topic(
    name: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    topic = await _load_by_name(db, user, name)
    await db.delete(topic)
    await db.commit()
