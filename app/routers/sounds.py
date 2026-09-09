"""Sound CRUD (cookie-authenticated, per-user scope).

Mirrors app/routers/topics.py structure. Each Sound belongs to one user;
another user's sound is a 404 (never 403) — same convention as topics.

Endpoints:
  GET    /api/sounds            list current user's sounds
  POST   /api/sounds            create sound (201)
  PATCH  /api/sounds/{sound_id} partial update
  DELETE /api/sounds/{sound_id} delete (204) — attached topics detach via FK ON DELETE SET NULL
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import get_current_user
from app.models import Sound, User
from app.schemas import SoundIn, SoundOut, SoundPatch

router = APIRouter(prefix="/api/sounds", tags=["sounds"])


def _to_out(s: Sound) -> SoundOut:
    return SoundOut(
        id=str(s.id),
        name=s.name,
        url=s.url,
        created_at=s.created_at,
    )


async def _load(
    db: AsyncSession, user: User, sound_id: str
) -> Sound:
    try:
        sid = uuid.UUID(sound_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Sound not found"
        )
    row = await db.execute(
        select(Sound).where(Sound.id == sid, Sound.user_id == user.id)
    )
    s = row.scalar_one_or_none()
    if s is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Sound not found"
        )
    return s


@router.get("", response_model=list[SoundOut])
async def list_sounds(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[SoundOut]:
    rows = await db.execute(
        select(Sound)
        .where(Sound.user_id == user.id)
        .order_by(Sound.created_at.desc())
    )
    return [_to_out(s) for s in rows.scalars().all()]


@router.get("/{sound_id}", response_model=SoundOut)
async def get_sound(
    sound_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SoundOut:
    return _to_out(await _load(db, user, sound_id))


@router.post("", response_model=SoundOut, status_code=status.HTTP_201_CREATED)
async def create_sound(
    body: SoundIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SoundOut:
    sound = Sound(user_id=user.id, name=body.name, url=body.url)
    db.add(sound)
    await db.commit()
    await db.refresh(sound)
    return _to_out(sound)


@router.patch("/{sound_id}", response_model=SoundOut)
async def patch_sound(
    sound_id: str,
    body: SoundPatch,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SoundOut:
    sound = await _load(db, user, sound_id)
    if body.name is not None:
        sound.name = body.name
    if body.url is not None:
        sound.url = body.url
    await db.commit()
    await db.refresh(sound)
    return _to_out(sound)


@router.delete("/{sound_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sound(
    sound_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    sound = await _load(db, user, sound_id)
    await db.delete(sound)
    await db.commit()
