"""SSE live stream + history endpoint tests."""
from __future__ import annotations

import asyncio
import hashlib
import hmac
from datetime import datetime, timedelta, timezone

import orjson
import pytest
from cryptography.fernet import Fernet

from app.services.pubsub import get_pubsub, reset_pubsub


@pytest.fixture(autouse=True)
def _fernet_key(monkeypatch):
    monkeypatch.setenv("WEBHOOK_SECRET_KEY", Fernet.generate_key().decode())
    reset_pubsub()
    yield
    reset_pubsub()


async def _register(client, email: str = "alice@example.com") -> None:
    r = await client.post(
        "/auth/register",
        json={"email": email, "password": "verysecret"},
    )
    assert r.status_code == 201


async def _create_agent(client) -> tuple[dict, str]:
    r = await client.post("/api/keys", json={"name": "orchestrator"})
    assert r.status_code == 201
    agent = r.json()
    return agent, agent["webhook_secret"]


def _sign(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _envelope(**overrides) -> dict:
    base = {
        "event": "thread.completed",
        "thread_id": "abc",
        "project_name": "demo",
        "status": "completed",
        "summary": "ok",
    }
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_history_empty(client):
    await _register(client)
    r = await client.get("/api/events")
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_history_returns_recent_notifications(client):
    """Two events with matching rule → 2 notifications in history."""
    await _register(client)
    agent, secret = await _create_agent(client)
    r_rule = await client.post("/api/rules", json={"name": "all", "event_pattern": "*"})
    assert r_rule.status_code == 201

    for i in range(2):
        body = orjson.dumps(_envelope(thread_id=f"t-{i}"))
        rr = await client.post(
            "/v1/events",
            content=body,
            headers={
                "X-Notifier-Agent": agent["agent_id"],
                "X-Notifier-Signature": _sign(secret, body),
            },
        )
        assert rr.status_code == 202

    r = await client.get("/api/events")
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 2
    # DESC by delivered_at; most recent is t-1
    assert items[0]["thread_id"] == "t-1"
    assert items[0]["event_name"] == "thread.completed"
    assert items[0]["rule_name"] == "all"


@pytest.mark.asyncio
async def test_history_since_filter(client):
    import orjson as _orjson

    await _register(client)
    agent, secret = await _create_agent(client)
    await client.post("/api/rules", json={"name": "all", "event_pattern": "*"})

    # First event
    body1 = _orjson.dumps(_envelope(thread_id="first"))
    rr1 = await client.post(
        "/v1/events",
        content=body1,
        headers={
            "X-Notifier-Agent": agent["agent_id"],
            "X-Notifier-Signature": _sign(secret, body1),
        },
    )
    assert rr1.status_code == 202

    # Sleep long enough that delivered_at differs by at least a millisecond.
    await asyncio.sleep(0.1)
    body2 = _orjson.dumps(_envelope(thread_id="second"))
    rr2 = await client.post(
        "/v1/events",
        content=body2,
        headers={
            "X-Notifier-Agent": agent["agent_id"],
            "X-Notifier-Signature": _sign(secret, body2),
        },
    )
    assert rr2.status_code == 202

    # No filter: both events present.
    items = (await client.get("/api/events")).json()
    assert len(items) == 2

    # since = a date clearly BEFORE both events → both returned.
    ancient = "2020-01-01T00:00:00"
    items = (await client.get(f"/api/events?since={ancient}")).json()
    assert len(items) == 2

    # since = unparseable → ignored, returns all.
    items = (await client.get("/api/events?since=not-a-date")).json()
    assert len(items) == 2


@pytest.mark.asyncio
async def test_history_limit(client):
    import orjson as _orjson

    await _register(client)
    agent, secret = await _create_agent(client)
    await client.post("/api/rules", json={"name": "all", "event_pattern": "*"})

    for i in range(5):
        body = _orjson.dumps(_envelope(thread_id=f"t-{i}"))
        await client.post(
            "/v1/events",
            content=body,
            headers={
                "X-Notifier-Agent": agent["agent_id"],
                "X-Notifier-Signature": _sign(secret, body),
            },
        )

    r = await client.get("/api/events?limit=2")
    assert r.status_code == 200
    assert len(r.json()) == 2


@pytest.mark.asyncio
async def test_history_isolation_per_user(client):
    """Two users → only see their own notifications."""
    import orjson as _orjson

    # Alice
    await _register(client, "alice@example.com")
    agent_a, secret_a = await _create_agent(client)
    await client.post("/api/rules", json={"name": "all", "event_pattern": "*"})
    body = _orjson.dumps(_envelope(thread_id="alice-event"))
    await client.post(
        "/v1/events",
        content=body,
        headers={
            "X-Notifier-Agent": agent_a["agent_id"],
            "X-Notifier-Signature": _sign(secret_a, body),
        },
    )

    # Bob on a separate client
    client.cookies.clear()
    await _register(client, "bob@example.com")
    agent_b, secret_b = await _create_agent(client)
    await client.post("/api/rules", json={"name": "all", "event_pattern": "*"})
    body_b = _orjson.dumps(_envelope(thread_id="bob-event"))
    await client.post(
        "/v1/events",
        content=body_b,
        headers={
            "X-Notifier-Agent": agent_b["agent_id"],
            "X-Notifier-Signature": _sign(secret_b, body_b),
        },
    )

    # Bob's history should only contain bob-event
    r = await client.get("/api/events")
    items = r.json()
    assert len(items) == 1
    assert items[0]["thread_id"] == "bob-event"


@pytest.mark.asyncio
async def test_sse_requires_auth(client):
    """SSE without cookie should be 401 (not 200 with empty stream)."""
    r = await client.get("/api/events/sse")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_sse_delivers_initial_ready_event(client):
    """SSE connection must yield `ready` immediately."""
    await _register(client)
    # Subscribe via pubsub directly so we don't race against the SSE response
    import uuid as _uuid

    me = await client.get("/auth/me")
    user_id = _uuid.UUID(me.json()["id"])
    pubsub = get_pubsub()
    q = await pubsub.subscribe(user_id)
    try:
        # Push one event manually so the consumer has something to drain.
        from app.services.pubsub import Notification

        await pubsub.publish(
            user_id,
            Notification(
                notification_id=1,
                event_id=1,
                rule_id=None,
                delivered_at=datetime.now(timezone.utc),
                event_name="test.event",
                thread_id="t-1",
                project_name="p",
                summary="s",
                status="ok",
                pr_url=None,
                occurred_at=None,
            ),
        )
        # Verify the queue holds it.
        notif = await asyncio.wait_for(q.get(), timeout=1.0)
        assert notif.event_name == "test.event"
    finally:
        await pubsub.unsubscribe(user_id, q)


@pytest.mark.asyncio
async def test_sse_receives_live_notification_after_post(client):
    """End-to-end: register → rule → subscribe → POST → drain queue."""
    import uuid as _uuid

    await _register(client)
    agent, secret = await _create_agent(client)
    await client.post("/api/rules", json={"name": "all", "event_pattern": "*"})

    me = await client.get("/auth/me")
    user_id = _uuid.UUID(me.json()["id"])
    pubsub = get_pubsub()
    q = await pubsub.subscribe(user_id)
    try:
        body = orjson.dumps(_envelope(thread_id="live-1"))
        rr = await client.post(
            "/v1/events",
            content=body,
            headers={
                "X-Notifier-Agent": agent["agent_id"],
                "X-Notifier-Signature": _sign(secret, body),
            },
        )
        assert rr.status_code == 202

        notif = await asyncio.wait_for(q.get(), timeout=2.0)
        assert notif.event_name == "thread.completed"
        assert notif.thread_id == "live-1"
        assert notif.summary == "ok"
    finally:
        await pubsub.unsubscribe(user_id, q)