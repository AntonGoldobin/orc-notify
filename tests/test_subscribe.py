"""Subscribe endpoint tests — GET /<topic>/{json,sse,raw,auth}."""
from __future__ import annotations

import asyncio
import json

import orjson
import pytest
from cryptography.fernet import Fernet

from app.services.pubsub_topics import reset_topic_pubsub


@pytest.fixture(autouse=True)
def _fernet_key(monkeypatch):
    monkeypatch.setenv("WEBHOOK_SECRET_KEY", Fernet.generate_key().decode())
    reset_topic_pubsub()
    yield
    reset_topic_pubsub()


async def _setup_user_topic(client, name: str = "alerts") -> None:
    await client.post(
        "/auth/register",
        json={"email": "alice@example.com", "password": "verysecret"},
    )
    await client.post("/api/topics", json={"name": name})


async def _setup_user_topic_with_key(client, name: str = "alerts") -> tuple[str, str]:
    """Returns (key_id, secret)."""
    await _setup_user_topic(client, name)
    r = await client.post(
        f"/api/topics/{name}/keys", json={"name": "publisher"}
    )
    body = r.json()
    return body["id"], body["secret"]


# ── /<topic>/json — poll ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_json_empty(client):
    await _setup_user_topic(client)
    r = await client.get("/alerts/json")
    assert r.status_code == 200
    # JSON array (we use application/x-ndjson but parse as JSON for testing).
    body = orjson.loads(r.content)
    assert body == []


@pytest.mark.asyncio
async def test_json_returns_published_messages(client):
    await _setup_user_topic(client)
    await client.post(
        "/alerts",
        content=b"hello",
        headers={"Content-Type": "text/plain"},
    )
    await client.post(
        "/alerts",
        content=b"world",
        headers={"Content-Type": "text/plain"},
    )
    r = await client.get("/alerts/json")
    assert r.status_code == 200
    body = orjson.loads(r.content)
    assert len(body) == 2
    assert body[0]["message"] == "hello"
    assert body[1]["message"] == "world"


@pytest.mark.asyncio
async def test_json_since_filter(client):
    import time as _time

    await _setup_user_topic(client)
    await client.post("/alerts", content=b"first")
    cutoff = int(_time.time())
    await asyncio.sleep(1.1)  # ensure next message has time > cutoff
    await client.post("/alerts", content=b"second")

    r = await client.get(f"/alerts/json?since={cutoff}")
    body = orjson.loads(r.content)
    assert len(body) == 1
    assert body[0]["message"] == "second"


@pytest.mark.asyncio
async def test_json_unknown_topic_404(client):
    await client.post(
        "/auth/register",
        json={"email": "alice@example.com", "password": "verysecret"},
    )
    r = await client.get("/no-such-topic/json")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_json_no_auth_401(client):
    r = await client.get("/alerts/json")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_json_other_users_topic_404(client):
    """Alice publishes; Bob's GET for Alice's topic → 404."""
    await _setup_user_topic(client, "alice-topic")
    await client.post("/alice-topic", content=b"hi")

    client.cookies.clear()
    await client.post(
        "/auth/register",
        json={"email": "bob@example.com", "password": "anotherpass"},
    )
    r = await client.get("/alice-topic/json")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_json_with_bearer_key(client):
    key_id, _secret = await _setup_user_topic_with_key(client, "alerts")
    await client.post("/alerts", content=b"hi")
    headers = {"Authorization": f"Bearer {key_id}.x"}

    r = await client.get("/alerts/json", headers=headers)
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_json_with_read_only_bearer(client):
    """Bearer with only 'read' scope can poll /json."""
    await _setup_user_topic(client, "alerts")
    r = await client.post(
        "/api/topics/alerts/keys",
        json={"name": "reader", "scopes": "read"},
    )
    key_id = r.json()["id"]
    await client.post("/alerts", content=b"hi")

    headers = {"Authorization": f"Bearer {key_id}.x"}
    r2 = await client.get("/alerts/json", headers=headers)
    assert r2.status_code == 200


@pytest.mark.asyncio
async def test_json_with_publish_only_bearer_403(client):
    """Bearer with only 'publish' scope CANNOT read."""
    await _setup_user_topic(client, "alerts")
    r = await client.post(
        "/api/topics/alerts/keys",
        json={"name": "pub", "scopes": "publish"},
    )
    key_id = r.json()["id"]
    headers = {"Authorization": f"Bearer {key_id}.x"}
    r2 = await client.get("/alerts/json", headers=headers)
    assert r2.status_code == 403


@pytest.mark.asyncio
async def test_json_bearer_wrong_topic_403(client):
    key_id, _ = await _setup_user_topic_with_key(client, "alerts")
    headers = {"Authorization": f"Bearer {key_id}.x"}
    r = await client.get("/other-topic/json", headers=headers)
    assert r.status_code == 403


# ── /<topic>/sse — SSE stream ─────────────────────────────────────


@pytest.mark.asyncio
async def test_sse_no_auth_401(client):
    r = await client.get("/alerts/sse")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_sse_receives_message_via_pubsub(client):
    """End-to-end: subscribe → publish via POST → message appears in queue."""
    await _setup_user_topic(client, "alerts")

    # Subscribe via the pubsub directly (we don't want to fight the SSE response).
    import uuid as _uuid

    me = (await client.get("/auth/me")).json()
    user_id = _uuid.UUID(me["id"])

    from app.services.pubsub_topics import TopicMessage, get_topic_pubsub
    pubsub = get_topic_pubsub()
    sub_id, q = await pubsub.subscribe(_uuid.UUID((await _get_topic_id(client, "alerts"))))
    try:
        # Publish via HTTP.
        r = await client.post("/alerts", content=b"live-1")
        assert r.status_code == 201

        msg = await asyncio.wait_for(q.get(), timeout=2.0)
        assert msg.payload["message"] == "live-1"
        assert msg.payload["topic"] == "alerts"
    finally:
        await pubsub.unsubscribe(_uuid.UUID((await _get_topic_id(client, "alerts"))), sub_id)


async def _get_topic_id(client, name: str) -> str:
    r = await client.get(f"/api/topics/{name}")
    return r.json()["id"]


@pytest.mark.asyncio
async def test_sse_unknown_topic_404(client):
    await client.post(
        "/auth/register",
        json={"email": "alice@example.com", "password": "verysecret"},
    )
    r = await client.get("/no-such-topic/sse")
    assert r.status_code == 404


# ── /<topic>/raw — line-delimited JSON ────────────────────────────


@pytest.mark.asyncio
async def test_raw_returns_messages(client):
    await _setup_user_topic(client, "alerts")
    await client.post("/alerts", content=b"one")
    await client.post("/alerts", content=b"two")

    r = await client.get("/alerts/raw")
    assert r.status_code == 200
    lines = [line for line in r.text.split("\n") if line]
    assert len(lines) == 2
    msg0 = orjson.loads(lines[0])
    msg1 = orjson.loads(lines[1])
    assert msg0["message"] == "one"
    assert msg1["message"] == "two"


@pytest.mark.asyncio
async def test_raw_empty(client):
    await _setup_user_topic(client, "alerts")
    r = await client.get("/alerts/raw")
    assert r.status_code == 200
    assert r.text == ""


# ── /<topic>/auth — capability probe ─────────────────────────────


@pytest.mark.asyncio
async def test_auth_probe_200(client):
    await _setup_user_topic(client, "alerts")
    r = await client.get("/alerts/auth")
    assert r.status_code == 200
    body = r.json()
    assert body["can_read"] is True
    assert body["topic"] == "alerts"


@pytest.mark.asyncio
async def test_auth_probe_no_auth_401(client):
    r = await client.get("/alerts/auth")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_auth_probe_unknown_topic_404(client):
    await client.post(
        "/auth/register",
        json={"email": "alice@example.com", "password": "verysecret"},
    )
    r = await client.get("/no-such-topic/auth")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_auth_probe_with_bearer(client):
    key_id, _ = await _setup_user_topic_with_key(client, "alerts")
    r = await client.get(
        "/alerts/auth", headers={"Authorization": f"Bearer {key_id}.x"}
    )
    assert r.status_code == 200
