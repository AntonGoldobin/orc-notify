"""Rules CRUD.

Endpoints (all auth-guarded, scoped to current user):
  - GET    /api/rules                  list user's rules (DESC by created_at)
  - POST   /api/rules                  create rule (single-use) — returns 422 on bad pattern/channel
  - PUT    /api/rules/{id}             partial update (name / event_pattern / channel / enabled)
  - DELETE /api/rules/{id}             204

Pattern semantics: fnmatch (case-sensitive, '*' matches everything except '/',
but event names have no '/' so '*' is effectively 'match all'). An explicit
'*' is the recommended "send everything" rule; 'thread.*' matches all events
starting with 'thread.'.
"""
from __future__ import annotations

from fnmatch import translate

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import get_current_user
from app.models import Rule, User
from app.schemas import RuleIn, RuleOut, RulePatch

router = APIRouter(prefix="/api/rules", tags=["rules"])


# ── Helpers ────────────────────────────────────────────────────────


SUPPORTED_CHANNELS = {"sse"}


def _validate_pattern(pattern: str) -> None:
    """Compile the glob via fnmatch.translate; raises ValueError on truly broken input.

    fnmatch is permissive — most strings compile, but we still want to surface
    things like embedded null bytes or patterns that include path separators.
    """
    try:
        translate(pattern)
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"invalid event_pattern: {exc}",
        )


def _validate_channel(channel: str) -> None:
    if channel not in SUPPORTED_CHANNELS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"unsupported channel '{channel}'; only {sorted(SUPPORTED_CHANNELS)} in v1",
        )


def _to_out(rule: Rule) -> RuleOut:
    return RuleOut(
        id=str(rule.id),
        name=rule.name,
        event_pattern=rule.event_pattern,
        channel=rule.channel,
        enabled=rule.enabled,
        created_at=rule.created_at,
        updated_at=rule.updated_at,
    )


async def _load(db: AsyncSession, user: User, rule_id: str) -> Rule:
    try:
        from uuid import UUID as _UUID

        rid = _UUID(rule_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found"
        )
    rule = await db.get(Rule, rid)
    if rule is None or rule.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found"
        )
    return rule


# ── Endpoints ──────────────────────────────────────────────────────


@router.get("", response_model=list[RuleOut])
async def list_rules(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[RuleOut]:
    rows = await db.execute(
        select(Rule).where(Rule.user_id == user.id).order_by(Rule.created_at.desc())
    )
    return [_to_out(r) for r in rows.scalars().all()]


@router.post("", response_model=RuleOut, status_code=status.HTTP_201_CREATED)
async def create_rule(
    body: RuleIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RuleOut:
    _validate_channel(body.channel)
    _validate_pattern(body.event_pattern)
    rule = Rule(
        user_id=user.id,
        name=body.name,
        event_pattern=body.event_pattern,
        channel=body.channel,
        enabled=body.enabled,
    )
    db.add(rule)
    await db.commit()
    return _to_out(rule)


@router.put("/{rule_id}", response_model=RuleOut)
async def update_rule(
    rule_id: str,
    body: RulePatch,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RuleOut:
    rule = await _load(db, user, rule_id)
    if body.name is not None:
        rule.name = body.name
    if body.event_pattern is not None:
        _validate_pattern(body.event_pattern)
        rule.event_pattern = body.event_pattern
    if body.channel is not None:
        _validate_channel(body.channel)
        rule.channel = body.channel
    if body.enabled is not None:
        rule.enabled = body.enabled
    await db.commit()
    await db.refresh(rule)
    return _to_out(rule)


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule(
    rule_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    rule = await _load(db, user, rule_id)
    await db.delete(rule)
    await db.commit()