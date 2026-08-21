"""Event persistence + rule fan-out.

The orchestrator POSTs one signed envelope per orchestrated thread. We:
  1. INSERT into events (one row per webhook hit)
  2. SELECT enabled rules for this user where fnmatch(event_pattern, event.event)
  3. INSERT one in_app_notifications row per matching rule
  4. UPDATE agents.last_event_at = now()
  5. Publish Notification to the per-user SSE pub/sub (best-effort)

All steps run inside one DB transaction; failure rolls back the whole batch
so we never get partial state (event row without notifications, etc).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from fnmatch import fnmatchcase
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Agent, Event, InAppNotification, Rule
from app.services.pubsub import Notification, get_pubsub


def _matches(event_name: str, pattern: str) -> bool:
    """Glob match. We use fnmatchcase so patterns are case-sensitive — event
    names are lowercase by convention. A literal '*' matches everything.
    """
    return fnmatchcase(event_name, pattern)


async def enqueue_event(
    db: AsyncSession,
    agent: Agent,
    payload: dict[str, Any],
    *,
    received_at: datetime | None = None,
) -> tuple[Event, list[InAppNotification]]:
    """Persist the event + fan-out to matching rules + update agent health.

    Returns the inserted Event and the inserted InAppNotification rows.
    """
    if received_at is None:
        received_at = datetime.now(timezone.utc)

    event = Event(
        user_id=agent.user_id,
        agent_id=agent.id,
        event=payload.get("event", ""),
        thread_id=payload.get("thread_id"),
        project_name=payload.get("project_name"),
        user_input=payload.get("user_input"),
        summary=payload.get("summary"),
        status=payload.get("status"),
        duration_seconds=payload.get("duration_seconds"),
        tasks_count=payload.get("tasks_count"),
        errors_count=payload.get("errors_count"),
        pr_url=payload.get("pr_url"),
        occurred_at=_parse_dt(payload.get("occurred_at")),
        received_at=received_at,
    )
    db.add(event)
    await db.flush()  # populate event.id for FK

    # Rule fan-out: only enabled rules for this user whose pattern matches.
    rules_q = await db.execute(
        select(Rule).where(Rule.user_id == agent.user_id, Rule.enabled.is_(True))
    )
    matching_rules = [r for r in rules_q.scalars() if _matches(event.event, r.event_pattern)]

    notifications: list[InAppNotification] = []
    for rule in matching_rules:
        notif = InAppNotification(
            user_id=agent.user_id, event_id=event.id, rule_id=rule.id
        )
        db.add(notif)
        notifications.append(notif)
    await db.flush()

    # Bump agent.last_event_at
    await db.execute(
        update(Agent).where(Agent.id == agent.id).values(last_event_at=received_at)
    )
    await db.commit()
    # No db.refresh — Python-side defaults populated event.id via flush, and
    # delivered_at is filled by server_default; no need to round-trip.

    # Best-effort SSE publish (in-memory only; no cross-instance fan-out).
    pubsub = get_pubsub()
    for n in notifications:
        notif_obj = Notification(
            notification_id=n.id,
            event_id=event.id,
            rule_id=n.rule_id,
            delivered_at=n.delivered_at,
            event_name=event.event,
            thread_id=event.thread_id,
            project_name=event.project_name,
            summary=event.summary,
            status=event.status,
            pr_url=event.pr_url,
            occurred_at=event.occurred_at,
        )
        await pubsub.publish(agent.user_id, notif_obj)

    return event, notifications


def _parse_dt(value: Any) -> datetime | None:
    """Parse an ISO-8601 string from the webhook payload. Returns None on missing
    or malformed input — agents may not always populate `occurred_at`.
    """
    if not value or not isinstance(value, str):
        return None
    try:
        # Python 3.11+ accepts the trailing 'Z' in fromisoformat.
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


async def get_user_notifications(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    since: datetime | None = None,
    limit: int = 50,
) -> list[tuple[InAppNotification, Event, Rule | None]]:
    """Join query used by SSE history endpoint (N6) and dashboard feed (N8).

    Returns tuples (notification, event, rule) ordered by delivered_at DESC.
    `since` filters to notifications delivered at or after this timestamp.
    """
    from sqlalchemy.orm import selectinload  # local to avoid eager-load on hot path

    q = (
        select(InAppNotification, Event, Rule)
        .join(Event, Event.id == InAppNotification.event_id)
        .outerjoin(Rule, Rule.id == InAppNotification.rule_id)
        .where(InAppNotification.user_id == user_id)
        .order_by(InAppNotification.delivered_at.desc())
        .limit(limit)
    )
    if since is not None:
        q = q.where(InAppNotification.delivered_at >= since)
    rows = await db.execute(q)
    return [(n, e, r) for n, e, r in rows.all()]