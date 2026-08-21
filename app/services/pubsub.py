"""In-process per-user pub/sub for SSE delivery.

Single-instance only: queues are kept in memory, not synced across workers.
For multi-instance deployment we would need Redis pub/sub or NATS — out of
scope for v1, documented in the plan.

Thread-safety: all mutations go through `asyncio.Lock`. We hold the lock only
for the duration of dict.set/queue.put, never across user code, so contention
is bounded.
"""
from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class Notification:
    """What we hand to SSE clients. Plain dicts would also work; a dataclass
    documents the shape and survives schema drift via type checking.
    """

    notification_id: int
    event_id: int
    rule_id: uuid.UUID | None
    delivered_at: datetime
    event_name: str
    thread_id: str | None
    project_name: str | None
    summary: str | None
    status: str | None
    pr_url: str | None
    occurred_at: datetime | None


class UserPubSub:
    def __init__(self) -> None:
        self._subs: dict[uuid.UUID, set[asyncio.Queue[Notification]]] = {}
        self._lock = asyncio.Lock()

    async def subscribe(self, user_id: uuid.UUID) -> asyncio.Queue[Notification]:
        q: asyncio.Queue[Notification] = asyncio.Queue(maxsize=200)
        async with self._lock:
            self._subs.setdefault(user_id, set()).add(q)
        return q

    async def unsubscribe(self, user_id: uuid.UUID, q: asyncio.Queue[Notification]) -> None:
        async with self._lock:
            subs = self._subs.get(user_id)
            if subs is None:
                return
            subs.discard(q)
            if not subs:
                self._subs.pop(user_id, None)

    async def publish(self, user_id: uuid.UUID, notif: Notification) -> int:
        """Fan-out to all subscribers. Returns count of successful enqueues.

        A full queue silently drops the message for that subscriber — we don't
        block the publisher. SSE is best-effort; if the client can't keep up,
        they reconnect and fetch history via the REST endpoint.
        """
        delivered = 0
        async with self._lock:
            subs = list(self._subs.get(user_id, ()))
        for q in subs:
            try:
                q.put_nowait(notif)
                delivered += 1
            except asyncio.QueueFull:
                # Slow consumer — drop silently. They can catch up via history.
                pass
        return delivered


_pubsub_instance: UserPubSub | None = None


def get_pubsub() -> UserPubSub:
    global _pubsub_instance
    if _pubsub_instance is None:
        _pubsub_instance = UserPubSub()
    return _pubsub_instance


def reset_pubsub() -> None:
    """For tests — drop the singleton so a fresh instance is built on next use."""
    global _pubsub_instance
    _pubsub_instance = None