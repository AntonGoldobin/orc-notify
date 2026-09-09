"""Publish a message to a topic — validate, idempotency-check, INSERT, fan-out.

Idempotency contract:
  - Client may set `Id:` header (stored as `external_id`).
  - If a row with the same (topic_id, external_id) exists, return it as-is
    with `created=False` (HTTP 200 instead of 201).
  - No `Id:` header → always create a new row (HTTP 201).

ponytail: idempotency lookup is a single SELECT before INSERT. Race window
between SELECT and INSERT is closed by the UNIQUE(topic_id, external_id)
constraint — a concurrent publisher hits IntegrityError and we retry the
SELECT to return the winning row. O(1) extra query on the rare conflict path.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Message, Topic
from app.schemas import format_tags_csv, parse_tags_csv
from app.services.pubsub_topics import TopicMessage, get_topic_pubsub


@dataclass(slots=True)
class PublishResult:
    """What the publish endpoint returns. `created=False` → 200, True → 201."""

    message: Message
    topic: Topic
    created: bool


async def publish_message(
    db: AsyncSession,
    topic: Topic,
    *,
    body: bytes,
    title: str | None,
    priority: int | None,
    tags_csv: str | None,
    click: str | None,
    icon: str | None,
    actions: list[dict] | None,
    external_id: str | None,
    content_type: str,
) -> PublishResult:
    """Insert the message (or return the existing one if `external_id` collides)
    and fan-out to the in-process pubsub.

    Caller owns the transaction (calls `await db.commit()` afterwards).
    """
    # Idempotency: if external_id is provided and we already have a row, return it.
    if external_id:
        existing = await db.execute(
            select(Message).where(
                Message.topic_id == topic.id, Message.external_id == external_id
            )
        )
        found = existing.scalar_one_or_none()
        if found is not None:
            return PublishResult(message=found, topic=topic, created=False)

    # Server-generated id: uuid4 hex (32 chars). Sortable in practice via
    # `time` BIGINT. Stdlib only; no extra dep.
    msg = Message(
        id=uuid.uuid4().hex,
        topic_id=topic.id,
        external_id=external_id,
        time=int(time.time()),
        event="message",
        title=title,
        body=body.decode("utf-8", errors="replace"),
        priority=(
            priority if priority is not None else topic.default_priority
        ),
        tags=format_tags_csv(parse_tags_csv(tags_csv)),
        click=click,
        icon=icon,
        actions=actions,
        content_type=content_type,
    )
    db.add(msg)
    try:
        await db.flush()
    except IntegrityError:
        # Race: a concurrent publisher beat us to (topic_id, external_id).
        # Roll back and re-fetch the winning row.
        await db.rollback()
        if external_id is None:
            # No external_id — unique violation is impossible here. Re-raise.
            raise
        existing = await db.execute(
            select(Message).where(
                Message.topic_id == topic.id, Message.external_id == external_id
            )
        )
        found = existing.scalar_one_or_none()
        if found is None:
            # Truly unexpected — surface as 500.
            raise
        return PublishResult(message=found, topic=topic, created=False)

    # Fan-out (in-process; single-instance). Don't fail the publish on pubsub errors.
    pubsub = get_topic_pubsub()
    payload = message_to_payload(msg, topic_name=topic.name)
    await pubsub.publish(
        topic.id,
        TopicMessage(topic_id=topic.id, payload=payload, topic_name=topic.name),
    )

    return PublishResult(message=msg, topic=topic, created=True)


def message_to_payload(msg: Message, *, topic_name: str) -> dict[str, Any]:
    """Serialize a Message row to the ntfy.sh wire format.

    Matches the example in redesign-ntfy-style.md §2.1.
    """
    return {
        "id": msg.id,
        "time": msg.time,
        "event": msg.event,
        "topic": topic_name,
        "title": msg.title,
        "message": msg.body,
        "priority": msg.priority,
        "tags": parse_tags_csv(msg.tags),
        "click": msg.click,
        "icon": msg.icon,
        "actions": msg.actions,
        "content_type": msg.content_type,
    }
