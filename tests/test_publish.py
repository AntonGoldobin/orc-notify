"""Publish endpoint tests — POST /<topic> with Bearer or cookie auth."""
from __future__ import annotations

import time

import orjson
import pytest
from cryptography.fernet import Fernet

from app.security import compute_topic_signature


@pytest.fixture(autouse=True)
def _fernet_key(monkeypatch):
    monkeypatch.setenv("WEBHOOK_SECRET_KEY", Fernet.generate_key().decode())


async def _register_create_topic_create_key(
    client, topic_name: str = "alerts"
) -> tuple[str, str]:
    """Returns (key_id, secret)."""
    r = await client.post(
        "/auth/register",
        json={"email": "alice@example.com", "password": "verysecret"},
    )
    assert r.status_code == 201
    r = await client.post("/api/topics", json={"name": topic_name})
    assert r.status_code == 201
    r = await client.post(
        f"/api/topics/{topic_name}/keys", json={"name": "publisher"}
    )
    assert r.status_code == 201
    body = r.json()
    return body["id"], body["secret"]


def _signed_headers(key_id: str, secret: str, body: bytes) -> dict:
    ts = str(int(time.time()))
    sig = compute_topic_signature(secret, body, ts)
    return {
        "Authorization": f"Bearer {key_id}.{sig}",
        "X-Notifier-Signature": sig,
        "X-Notifier-Timestamp": ts,
    }


# ── Cookie auth ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_publish_with_cookie_201(client):
    await client.post(
        "/auth/register",
        json={"email": "alice@example.com", "password": "verysecret"},
    )
    await client.post("/api/topics", json={"name": "alerts"})
    r = await client.post(
        "/alerts",
        content=b"hello world",
        headers={"Content-Type": "text/plain"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["message"] == "hello world"
    assert body["topic"] == "alerts"
    assert body["event"] == "message"
    assert body["priority"] == 3
    assert body["content_type"] == "text/plain"


@pytest.mark.asyncio
async def test_publish_with_headers(client):
    await client.post(
        "/auth/register",
        json={"email": "alice@example.com", "password": "verysecret"},
    )
    await client.post("/api/topics", json={"name": "alerts"})
    r = await client.post(
        "/alerts",
        content=b"deploy failed",
        headers={
            "Title": "Deploy failed",
            "Priority": "5",
            "Tags": "rotating_light,deploy,ci",
            "Click": "https://github.com/foo/bar/actions/runs/1",
            "Icon": "https://example.com/icon.png",
            "Id": "deploy-123",
            "Content-Type": "text/plain",
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert body["title"] == "Deploy failed"
    assert body["priority"] == 5
    assert body["tags"] == ["rotating_light", "deploy", "ci"]
    assert body["click"] == "https://github.com/foo/bar/actions/runs/1"
    assert body["icon"] == "https://example.com/icon.png"


@pytest.mark.asyncio
async def test_publish_idempotent_same_id_returns_200(client):
    await client.post(
        "/auth/register",
        json={"email": "alice@example.com", "password": "verysecret"},
    )
    await client.post("/api/topics", json={"name": "alerts"})

    r1 = await client.post(
        "/alerts",
        content=b"first",
        headers={"Id": "dup-1", "Content-Type": "text/plain"},
    )
    assert r1.status_code == 201

    r2 = await client.post(
        "/alerts",
        content=b"second",  # body is different — but Id collides
        headers={"Id": "dup-1", "Content-Type": "text/plain"},
    )
    assert r2.status_code == 200  # idempotent
    body = r2.json()
    assert body["message"] == "first"  # original returned
    assert body["id"] == r1.json()["id"]


@pytest.mark.asyncio
async def test_publish_unknown_topic_404(client):
    await client.post(
        "/auth/register",
        json={"email": "alice@example.com", "password": "verysecret"},
    )
    r = await client.post(
        "/no-such-topic",
        content=b"hello",
        headers={"Content-Type": "text/plain"},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_publish_no_auth_401(client):
    r = await client.post(
        "/anything",
        content=b"hello",
        headers={"Content-Type": "text/plain"},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_publish_empty_body_400(client):
    await client.post(
        "/auth/register",
        json={"email": "alice@example.com", "password": "verysecret"},
    )
    await client.post("/api/topics", json={"name": "alerts"})
    r = await client.post("/alerts", content=b"")
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_publish_invalid_priority_400(client):
    await client.post(
        "/auth/register",
        json={"email": "alice@example.com", "password": "verysecret"},
    )
    await client.post("/api/topics", json={"name": "alerts"})
    r = await client.post(
        "/alerts",
        content=b"hi",
        headers={"Priority": "9"},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_publish_non_integer_priority_400(client):
    await client.post(
        "/auth/register",
        json={"email": "alice@example.com", "password": "verysecret"},
    )
    await client.post("/api/topics", json={"name": "alerts"})
    r = await client.post(
        "/alerts",
        content=b"hi",
        headers={"Priority": "max"},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_publish_invalid_actions_json_400(client):
    await client.post(
        "/auth/register",
        json={"email": "alice@example.com", "password": "verysecret"},
    )
    await client.post("/api/topics", json={"name": "alerts"})
    r = await client.post(
        "/alerts",
        content=b"hi",
        headers={"Actions": "not-json"},
    )
    assert r.status_code == 400


# ── Bearer auth ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_publish_with_bearer_201(client):
    key_id, secret = await _register_create_topic_create_key(client, "alerts")
    body = b"hello via bearer"
    headers = _signed_headers(key_id, secret, body)
    headers["Content-Type"] = "text/plain"

    r = await client.post("/alerts", content=body, headers=headers)
    assert r.status_code == 201, r.text
    out = r.json()
    assert out["message"] == "hello via bearer"


@pytest.mark.asyncio
async def test_publish_bearer_wrong_signature_401(client):
    key_id, _secret = await _register_create_topic_create_key(client, "alerts")
    body = b"hello"
    ts = str(int(time.time()))
    headers = {
        "Authorization": f"Bearer {key_id}.deadbeef",
        "X-Notifier-Signature": "deadbeef",
        "X-Notifier-Timestamp": ts,
        "Content-Type": "text/plain",
    }
    r = await client.post("/alerts", content=body, headers=headers)
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_publish_bearer_stale_timestamp_401(client):
    key_id, secret = await _register_create_topic_create_key(client, "alerts")
    body = b"hello"
    ts = str(int(time.time()) - 1000)  # 16 minutes ago
    sig = compute_topic_signature(secret, body, ts)
    headers = {
        "Authorization": f"Bearer {key_id}.{sig}",
        "X-Notifier-Signature": sig,
        "X-Notifier-Timestamp": ts,
        "Content-Type": "text/plain",
    }
    r = await client.post("/alerts", content=body, headers=headers)
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_publish_bearer_wrong_topic_403(client):
    """Bearer key for 'alerts' cannot publish to 'other-topic'."""
    key_id, secret = await _register_create_topic_create_key(client, "alerts")
    body = b"hello"
    headers = _signed_headers(key_id, secret, body)
    headers["Content-Type"] = "text/plain"
    r = await client.post("/other-topic", content=body, headers=headers)
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_publish_bearer_unknown_key_401(client):
    body = b"hello"
    ts = str(int(time.time()))
    sig = compute_topic_signature("any-secret", body, ts)
    headers = {
        "Authorization": "Bearer 00000000-0000-0000-0000-000000000000.x",
        "X-Notifier-Signature": sig,
        "X-Notifier-Timestamp": ts,
        "Content-Type": "text/plain",
    }
    r = await client.post("/alerts", content=body, headers=headers)
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_publish_bearer_read_only_scope_403(client):
    """A key with only 'read' scope cannot publish."""
    await client.post(
        "/auth/register",
        json={"email": "alice@example.com", "password": "verysecret"},
    )
    await client.post("/api/topics", json={"name": "alerts"})
    r = await client.post(
        "/api/topics/alerts/keys",
        json={"name": "sub", "scopes": "read"},
    )
    key_id = r.json()["id"]
    secret = r.json()["secret"]

    body = b"hi"
    headers = _signed_headers(key_id, secret, body)
    headers["Content-Type"] = "text/plain"
    r2 = await client.post("/alerts", content=body, headers=headers)
    assert r2.status_code == 403
    assert "scope" in r2.json()["detail"].lower()


@pytest.mark.asyncio
async def test_publish_bearer_publish_only_scope_succeeds(client):
    """A key with only 'publish' scope can publish."""
    await client.post(
        "/auth/register",
        json={"email": "alice@example.com", "password": "verysecret"},
    )
    await client.post("/api/topics", json={"name": "alerts"})
    r = await client.post(
        "/api/topics/alerts/keys",
        json={"name": "pub", "scopes": "publish"},
    )
    key_id = r.json()["id"]
    secret = r.json()["secret"]

    body = b"hi"
    headers = _signed_headers(key_id, secret, body)
    headers["Content-Type"] = "text/plain"
    r2 = await client.post("/alerts", content=body, headers=headers)
    assert r2.status_code == 201


@pytest.mark.asyncio
async def test_publish_bearer_missing_signature_401(client):
    key_id, _secret = await _register_create_topic_create_key(client, "alerts")
    r = await client.post(
        "/alerts",
        content=b"hello",
        headers={
            "Authorization": f"Bearer {key_id}.x",
            "Content-Type": "text/plain",
        },
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_publish_uses_topic_default_priority(client):
    """No Priority header → topic's default_priority is used."""
    await client.post(
        "/auth/register",
        json={"email": "alice@example.com", "password": "verysecret"},
    )
    r = await client.post(
        "/api/topics", json={"name": "alerts", "default_priority": 5}
    )
    assert r.status_code == 201
    r2 = await client.post("/alerts", content=b"hi")
    assert r2.status_code == 201
    assert r2.json()["priority"] == 5


@pytest.mark.asyncio
async def test_publish_actions_json_array(client):
    await client.post(
        "/auth/register",
        json={"email": "alice@example.com", "password": "verysecret"},
    )
    await client.post("/api/topics", json={"name": "alerts"})
    actions = orjson.dumps(
        [{"action": "view", "label": "Open", "url": "https://example.com"}]
    ).decode()
    r = await client.post(
        "/alerts",
        content=b"hi",
        headers={"Actions": actions},
    )
    assert r.status_code == 201
    assert r.json()["actions"] == [
        {"action": "view", "label": "Open", "url": "https://example.com"}
    ]
