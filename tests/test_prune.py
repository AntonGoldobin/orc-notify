"""TTL prune task tests — verify expired messages are deleted, recent kept."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select, text

from app.models import Message, Topic, User
from app.services.prune import _prune_once


@pytest.fixture(autouse=True)
def _fernet_key(monkeypatch):
    monkeypatch.setenv("WEBHOOK_SECRET_KEY", Fernet.generate_key().decode())


async def _make_topic(db_session, retention_days: int = 7) -> tuple[User, Topic]:
    from app.security import hash_password

    user = User(
        email="alice@example.com",
        password_hash=hash_password("verysecret"),
    )
    db_session.add(user)
    await db_session.flush()
    topic = Topic(
        user_id=user.id,
        name="alerts",
        retention_days=retention_days,
    )
    db_session.add(topic)
    await db_session.commit()
    return user, topic


async def _make_message(
    db_session, topic: Topic, *, age_days: int, body: str = "x"
) -> Message:
    """Insert a message with `created_at` set to `age_days` ago."""
    # SQLite's default datetime adapter drops tzinfo, so we use naive UTC to
    # match the prune code's comparison. Postgres TIMESTAMPTZ stores the same
    # instant correctly.
    ts = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=age_days)
    m = Message(
        id=f"m-{age_days}-{body}",
        topic_id=topic.id,
        time=int(ts.timestamp()),
        body=body,
        content_type="text/plain",
    )
    db_session.add(m)
    await db_session.flush()
    await db_session.execute(
        text("UPDATE messages SET created_at = :ts WHERE id = :id"),
        {"ts": ts, "id": m.id},
    )
    await db_session.commit()
    return m


@pytest.mark.asyncio
async def test_prune_deletes_only_expired(db_session):
    """Messages older than retention_days get deleted; recent ones stay."""
    user, topic = await _make_topic(db_session, retention_days=7)

    fresh = await _make_message(db_session, topic, age_days=1, body="fresh")
    old = await _make_message(db_session, topic, age_days=10, body="old")

    deleted = await _prune_once(session=db_session)
    assert deleted == 1

    # Verify which one survived.
    remaining = (await db_session.execute(select(Message))).scalars().all()
    ids = {m.id for m in remaining}
    assert fresh.id in ids
    assert old.id not in ids


@pytest.mark.asyncio
async def test_prune_respects_per_topic_retention(db_session):
    """A topic with retention_days=2 should prune a 3-day-old message even
    when other topics have retention_days=30 and keep their old messages.
    """
    from app.security import hash_password

    user = User(
        email="alice@example.com",
        password_hash=hash_password("verysecret"),
    )
    db_session.add(user)
    await db_session.flush()

    short = Topic(user_id=user.id, name="short", retention_days=2)
    long = Topic(user_id=user.id, name="long", retention_days=30)
    db_session.add_all([short, long])
    await db_session.commit()

    short_old = await _make_message(db_session, short, age_days=3, body="s-old")
    short_recent = await _make_message(db_session, short, age_days=1, body="s-recent")
    long_old = await _make_message(db_session, long, age_days=20, body="l-old")
    long_recent = await _make_message(db_session, long, age_days=1, body="l-recent")

    deleted = await _prune_once(session=db_session)
    assert deleted == 1  # only the short-topic 3-day-old message

    remaining = (await db_session.execute(select(Message))).scalars().all()
    ids = {m.id for m in remaining}
    assert short_old.id not in ids  # pruned
    assert short_recent.id in ids
    assert long_old.id in ids  # kept (within 30 days)
    assert long_recent.id in ids


@pytest.mark.asyncio
async def test_prune_no_messages_returns_zero(db_session):
    user, topic = await _make_topic(db_session)
    deleted = await _prune_once(session=db_session)
    assert deleted == 0


@pytest.mark.asyncio
async def test_prune_all_recent_returns_zero(db_session):
    user, topic = await _make_topic(db_session, retention_days=7)
    await _make_message(db_session, topic, age_days=1, body="a")
    await _make_message(db_session, topic, age_days=3, body="b")
    deleted = await _prune_once(session=db_session)
    assert deleted == 0
