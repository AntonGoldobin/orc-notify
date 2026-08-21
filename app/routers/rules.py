"""Rules CRUD router.

N5 minimal stub: just POST so event-fan-out tests have a target. Full CRUD
(list/update/delete) + pattern validation lands in N7 — but the prefix and
shape are stable now so tests written against N5 don't need to change.
"""
from __future__ import annotations

from datetime import datetime
from fnmatch import fnmatchcase

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import get_current_user
from app.models import Rule, User

router = APIRouter(prefix="/api/rules", tags=["rules"])


class RuleIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    event_pattern: str = Field(min_length=1, max_length=255)
    channel: str = "sse"
    enabled: bool = True


class RuleOut(BaseModel):
    id: str
    name: str
    event_pattern: str
    channel: str
    enabled: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_rule(cls, r: Rule) -> "RuleOut":
        return cls(
            id=str(r.id),
            name=r.name,
            event_pattern=r.event_pattern,
            channel=r.channel,
            enabled=r.enabled,
            created_at=r.created_at,
            updated_at=r.updated_at,
        )


@router.post("", response_model=RuleOut, status_code=status.HTTP_201_CREATED)
async def create_rule(
    body: RuleIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RuleOut:
    if body.channel != "sse":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"unsupported channel '{body.channel}'; only 'sse' in v1",
        )
    # Validate the glob compiles — try a dummy match; raises nothing on bad
    # syntax (fnmatch is forgiving) but a ValueError on truly broken input.
    try:
        fnmatchcase("test.event", body.event_pattern)
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"invalid event_pattern: {exc}",
        )
    rule = Rule(
        user_id=user.id,
        name=body.name,
        event_pattern=body.event_pattern,
        channel=body.channel,
        enabled=body.enabled,
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return RuleOut.from_rule(rule)