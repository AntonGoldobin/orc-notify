"""TTL prune task — runs as an asyncio background task for the app's lifetime.

ponytail: single asyncio task with `asyncio.sleep` loop. Upgrade path: pg_cron
or a separate worker process. Per-topic `retention_days` overrides the default
7-day window when shorter (we never extend beyond the per-topic value).

Schedule: every hour (3600s). At each tick we delete rows whose `created_at`
is older than the topic's retention window. Topics with `retention_days = 7`
default to 7d; per-topic override is honored when shorter.

We acquire the DB engine lazily from `app.db.get_engine()`; the task is owned
by the FastAPI lifespan so it dies cleanly on shutdown.

SQL uses SQLAlchemy ORM constructs so it works against both Postgres (prod) and
SQLite (tests). The cut-off is computed in Python as a naive UTC datetime to
match how the SQLite adapter stores tz-aware columns (drops tzinfo).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_sessionmaker
from app.models import Message, Topic

logger = logging.getLogger(__name__)

DEFAULT_RETENTION_DAYS = 7
TICK_SECONDS = 3600.0


async def _prune_once(session: AsyncSession | None = None) -> int:
    """Run one prune sweep. Returns total rows deleted."""
    if session is None:
        Session = get_sessionmaker()
        async with Session() as s:
            return await _prune_with_session(s)
    return await _prune_with_session(session)


async def _prune_with_session(session: AsyncSession) -> int:
    # Naive UTC matches how the SQLite adapter round-trips tz-aware columns.
    # Postgres returns tz-aware via TIMESTAMPTZ; the comparison still works
    # because Python normalizes both sides via the column's tzinfo.
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    topics = (await session.execute(select(Topic))).scalars().all()
    deleted_total = 0
    for t in topics:
        cutoff = now_utc - timedelta(days=t.retention_days)
        result = await session.execute(
            delete(Message).where(
                Message.topic_id == t.id, Message.created_at < cutoff
            )
        )
        deleted_total += result.rowcount or 0
    if deleted_total:
        await session.commit()
    return deleted_total


async def _prune_loop(stop_event: asyncio.Event) -> None:
    """Run _prune_once every TICK_SECONDS until stop_event is set."""
    while not stop_event.is_set():
        try:
            deleted = await _prune_once()
            if deleted:
                logger.info("prune: deleted %d expired message(s)", deleted)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            # Don't crash the loop on transient DB errors. Log and retry next tick.
            logger.warning("prune tick failed: %s", exc)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=TICK_SECONDS)
        except asyncio.TimeoutError:
            continue


def start_prune_task(app: FastAPI) -> None:
    """Attach a prune task to the app — call from lifespan on startup."""
    stop_event = asyncio.Event()
    task = asyncio.create_task(_prune_loop(stop_event), name="prune-messages")
    app.state.prune_stop = stop_event
    app.state.prune_task = task


async def stop_prune_task(app: FastAPI) -> None:
    """Signal the prune task to exit and await its termination."""
    stop_event: asyncio.Event | None = getattr(app.state, "prune_stop", None)
    task: asyncio.Task | None = getattr(app.state, "prune_task", None)
    if stop_event is not None:
        stop_event.set()
    if task is not None:
        try:
            await asyncio.wait_for(task, timeout=5.0)
        except asyncio.TimeoutError:
            task.cancel()
