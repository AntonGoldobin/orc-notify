"""Webhook + event persistence + rule fan-out tests."""
from __future__ import annotations

import hashlib
import hmac

import pytest
from cryptography.fernet import Fernet

from app.services.pubsub import get_pubsub, reset_pubsub


@pytest.fixture(autouse=True)
def _reset_pubsub():
    """Each test gets a fresh pubsub so cross-test state can't leak."""
    reset_pubsub()
    yield
    reset_pubsub()


async def _register_and_create_agent(client) -> tuple[dict, dict, str]:
    r = await client.post(
        "/auth/register",
        json={"email": "alice@example.com", "password": "verysecret"},
    )
    assert r.status_code == 201
    user = r.json()
    r2 = await client.post("/api/keys", json={"name": "orchestrator"})
    assert r2.status_code == 201
    agent = r2.json()
    return user, agent, agent["webhook_secret"]


def _sign(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _envelope(**overrides) -> dict:
    base = {
        "event": "thread.completed",
        "thread_id": "abc123",
        "project_name": "reelant",
        "user_input": "add dark mode",
        "summary": "Implemented dark mode toggle",
        "status": "completed",
        "duration_seconds": 247.3,
        "tasks_count": 5,
        "errors_count": 0,
        "pr_url": "https://github.com/AntonGoldobin/reelant/pull/42",
        "occurred_at": "2026-08-21T10:05:30Z",
    }
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_post_event_persists_row(client):
    import orjson

    _, agent, secret = await _register_and_create_agent(client)
    body = orjson.dumps(_envelope())

    r = await client.post(
        "/v1/events",
        content=body,
        headers={
            "X-Notifier-Agent": agent["agent_id"],
            "X-Notifier-Signature": _sign(secret, body),
            "Content-Type": "application/json",
        },
    )
    assert r.status_code == 202, r.text
    body_out = r.json()
    assert body_out["event_id"] > 0
    assert body_out["matched_rule_count"] == 0  # no rules configured yet


@pytest.mark.asyncio
async def test_post_event_with_matching_rule_fans_out(client):
    import orjson

    _, agent, secret = await _register_and_create_agent(client)
    # Create one rule that matches.
    r_rule = await client.post(
        "/api/rules",
        json={"name": "everything", "event_pattern": "*"},
    )
    assert r_rule.status_code == 201

    body = orjson.dumps(_envelope(event="thread.completed"))
    r = await client.post(
        "/v1/events",
        content=body,
        headers={
            "X-Notifier-Agent": agent["agent_id"],
            "X-Notifier-Signature": _sign(secret, body),
        },
    )
    assert r.status_code == 202
    assert r.json()["matched_rule_count"] == 1


@pytest.mark.asyncio
async def test_post_event_with_glob_pattern_matches_thread_star(client):
    import orjson

    _, agent, secret = await _register_and_create_agent(client)
    r_rule = await client.post(
        "/api/rules",
        json={"name": "all-thread", "event_pattern": "thread.*"},
    )
    assert r_rule.status_code == 201

    # thread.completed should match
    body = orjson.dumps(_envelope(event="thread.completed"))
    r = await client.post(
        "/v1/events",
        content=body,
        headers={
            "X-Notifier-Agent": agent["agent_id"],
            "X-Notifier-Signature": _sign(secret, body),
        },
    )
    assert r.status_code == 202
    assert r.json()["matched_rule_count"] == 1

    # foo.completed should NOT match thread.*
    body2 = orjson.dumps(_envelope(event="foo.completed"))
    r2 = await client.post(
        "/v1/events",
        content=body2,
        headers={
            "X-Notifier-Agent": agent["agent_id"],
            "X-Notifier-Signature": _sign(secret, body2),
        },
    )
    assert r2.status_code == 202
    assert r2.json()["matched_rule_count"] == 0


@pytest.mark.asyncio
async def test_disabled_rule_does_not_match(client):
    import orjson

    _, agent, secret = await _register_and_create_agent(client)
    r_rule = await client.post(
        "/api/rules",
        json={"name": "everything", "event_pattern": "*", "enabled": False},
    )
    assert r_rule.status_code == 201

    body = orjson.dumps(_envelope())
    r = await client.post(
        "/v1/events",
        content=body,
        headers={
            "X-Notifier-Agent": agent["agent_id"],
            "X-Notifier-Signature": _sign(secret, body),
        },
    )
    assert r.status_code == 202
    assert r.json()["matched_rule_count"] == 0


@pytest.mark.asyncio
async def test_missing_signature_header_401(client):
    import orjson

    _, agent, _ = await _register_and_create_agent(client)
    body = orjson.dumps(_envelope())
    r = await client.post(
        "/v1/events",
        content=body,
        headers={"X-Notifier-Agent": agent["agent_id"]},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_wrong_signature_401(client):
    import orjson

    _, agent, _ = await _register_and_create_agent(client)
    body = orjson.dumps(_envelope())
    r = await client.post(
        "/v1/events",
        content=body,
        headers={
            "X-Notifier-Agent": agent["agent_id"],
            "X-Notifier-Signature": "0" * 64,  # valid length but wrong
        },
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_unknown_agent_404(client):
    import orjson

    await client.post(
        "/auth/register",
        json={"email": "alice@example.com", "password": "verysecret"},
    )
    body = orjson.dumps(_envelope())
    r = await client.post(
        "/v1/events",
        content=body,
        headers={
            "X-Notifier-Agent": "no-such-agent",
            "X-Notifier-Signature": _sign("doesnt-matter", body),
        },
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_missing_agent_header_401(client):
    import orjson

    body = orjson.dumps(_envelope())
    r = await client.post(
        "/v1/events",
        content=body,
        headers={"X-Notifier-Signature": _sign("x", body)},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_missing_event_field_422(client):
    import orjson

    _, agent, secret = await _register_and_create_agent(client)
    bad = _envelope()
    del bad["event"]
    body = orjson.dumps(bad)
    r = await client.post(
        "/v1/events",
        content=body,
        headers={
            "X-Notifier-Agent": agent["agent_id"],
            "X-Notifier-Signature": _sign(secret, body),
        },
    )
    assert r.status_code == 422
    assert "event" in r.json()["detail"]


@pytest.mark.asyncio
async def test_invalid_json_422(client):
    _, agent, secret = await _register_and_create_agent(client)
    body = b"this is not json"
    r = await client.post(
        "/v1/events",
        content=body,
        headers={
            "X-Notifier-Agent": agent["agent_id"],
            "X-Notifier-Signature": _sign(secret, body),
        },
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_pubsub_receives_notifications(client):
    """SSE-style subscriber gets notified on matching event."""
    import asyncio
    import orjson

    _, agent, secret = await _register_and_create_agent(client)
    await client.post("/api/rules", json={"name": "all", "event_pattern": "*"})

    # Get user_id from /me
    me_r = await client.get("/auth/me")
    user_id = me_r.json()["id"]

    # Subscribe BEFORE the POST
    pubsub = get_pubsub()
    import uuid as _uuid

    q = await pubsub.subscribe(_uuid.UUID(user_id))

    body = orjson.dumps(_envelope(event="thread.completed"))
    r = await client.post(
        "/v1/events",
        content=body,
        headers={
            "X-Notifier-Agent": agent["agent_id"],
            "X-Notifier-Signature": _sign(secret, body),
        },
    )
    assert r.status_code == 202

    # Drain the queue — expect exactly one Notification
    got = await asyncio.wait_for(q.get(), timeout=1.0)
    assert got.event_name == "thread.completed"
    assert got.thread_id == "abc123"
    assert got.project_name == "reelant"
    assert got.summary == "Implemented dark mode toggle"


@pytest.mark.asyncio
async def test_pubsub_unsubscribe_stops_delivery(client):
    import asyncio
    import orjson
    import uuid as _uuid

    _, agent, secret = await _register_and_create_agent(client)
    await client.post("/api/rules", json={"name": "all", "event_pattern": "*"})

    me_r = await client.get("/auth/me")
    user_id = _uuid.UUID(me_r.json()["id"])

    pubsub = get_pubsub()
    q = await pubsub.subscribe(user_id)
    await pubsub.unsubscribe(user_id, q)

    body = orjson.dumps(_envelope())
    r = await client.post(
        "/v1/events",
        content=body,
        headers={
            "X-Notifier-Agent": agent["agent_id"],
            "X-Notifier-Signature": _sign(secret, body),
        },
    )
    assert r.status_code == 202

    # Queue should be empty — no notifications after unsubscribe
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(q.get(), timeout=0.2)