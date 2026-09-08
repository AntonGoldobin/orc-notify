"""In-process per-topic pub/sub for SSE delivery.

Single-instance only — queues are kept in memory, not synced across workers.
For multi-instance deployment we'd need Postgres LISTEN/NOTIFY or Redis pub/sub.

ponytail: in-process dict keyed by (topic_id, subscriber_id). Single-instance
ceiling. Upgrade path: replace the dict with a Redis subscriber or a Postgres
LISTEN/NOTIFY loop; keep the same `subscribe / publish / unsubscribe / close`
interface so callers don't change.

Thread-safety: all mutations go through `asyncio.Lock`. We hold the lock only
for the duration of dict.set/queue.put, never across user code, so contention
is bounded.

Sub-keying: each subscriber gets a UUID (`subscriber_id`) and its own queue.
The fan-out iterates all queues for the topic, dropping silently on QueueFull
(slow consumer) — they can reconnect and fetch history via REST.
"""
from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class TopicMessage:
    """Plain dicts would also work; a dataclass documents the shape and
    survives schema drift via type checking. `payload` carries the MessageOut
    dict as constructed by the publish endpoint.
    """

    topic_id: uuid.UUID
    payload: dict[str, Any]


class TopicPubSub:
    def __init__(self) -> None:
        # topic_id → set of (subscriber_id, queue). The pair keeps
        # concurrent subscribers on the same topic from clobbering each other.
        self._subs: dict[uuid.UUID, dict[uuid.UUID, asyncio.Queue[TopicMessage]]] = {}
        self._lock = asyncio.Lock()

    async def subscribe(
        self, topic_id: uuid.UUID
    ) -> tuple[uuid.UUID, asyncio.Queue[TopicMessage]]:
        """Register a new subscriber. Returns (subscriber_id, queue) — caller
        passes both to unsubscribe on disconnect.
        """
        sub_id = uuid.uuid4()
        q: asyncio.Queue[TopicMessage] = asyncio.Queue(maxsize=200)
        async with self._lock:
            self._subs.setdefault(topic_id, {})[sub_id] = q
        return sub_id, q

    async def unsubscribe(
        self, topic_id: uuid.UUID, sub_id: uuid.UUID
    ) -> None:
        async with self._lock:
            topic_subs = self._subs.get(topic_id)
            if topic_subs is None:
                return
            topic_subs.pop(sub_id, None)
            if not topic_subs:
                self._subs.pop(topic_id, None)

    async def publish(self, topic_id: uuid.UUID, msg: TopicMessage) -> int:
        """Fan-out to all subscribers on this topic. Returns count of
        successful enqueues. A full queue silently drops the message for
        that subscriber — we don't block the publisher. SSE is best-effort;
        if the client can't keep up, they reconnect and fetch history.
        """
        delivered = 0
        async with self._lock:
            topic_subs = list(self._subs.get(topic_id, {}).items())
        for _sub_id, q in topic_subs:
            try:
                q.put_nowait(msg)
                delivered += 1
            except asyncio.QueueFull:
                # Slow consumer — drop silently. They can catch up via history.
                pass
        return delivered

    async def close(self) -> None:
        """Reset state — for tests."""
        async with self._lock:
            self._subs.clear()


_pubsub_instance: TopicPubSub | None = None


def get_topic_pubsub() -> TopicPubSub:
    global _pubsub_instance
    if _pubsub_instance is None:
        _pubsub_instance = TopicPubSub()
    return _pubsub_instance


def reset_topic_pubsub() -> None:
    """For tests — drop the singleton so a fresh instance is built on next use."""
    global _pubsub_instance
    _pubsub_instance = None
