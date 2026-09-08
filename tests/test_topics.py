"""Topic CRUD tests."""
from __future__ import annotations

import pytest
from cryptography.fernet import Fernet


@pytest.fixture(autouse=True)
def _fernet_key(monkeypatch):
    monkeypatch.setenv("WEBHOOK_SECRET_KEY", Fernet.generate_key().decode())


async def _register(client, email: str = "alice@example.com") -> None:
    r = await client.post(
        "/auth/register",
        json={"email": email, "password": "verysecret"},
    )
    assert r.status_code == 201


@pytest.mark.asyncio
async def test_create_topic(client):
    await _register(client)
    r = await client.post(
        "/api/topics", json={"name": "alerts", "description": "deploy alerts"}
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["name"] == "alerts"
    assert body["description"] == "deploy alerts"
    assert body["default_priority"] == 3
    assert body["retention_days"] == 7
    assert "id" in body


@pytest.mark.asyncio
async def test_create_topic_with_overrides(client):
    await _register(client)
    r = await client.post(
        "/api/topics",
        json={"name": "critical", "default_priority": 5, "retention_days": 30},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["default_priority"] == 5
    assert body["retention_days"] == 30


@pytest.mark.asyncio
async def test_create_topic_invalid_name_422(client):
    await _register(client)
    # Spaces not allowed
    r = await client.post("/api/topics", json={"name": "has spaces"})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_create_topic_empty_name_422(client):
    await _register(client)
    r = await client.post("/api/topics", json={"name": ""})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_create_duplicate_topic_409(client):
    await _register(client)
    r1 = await client.post("/api/topics", json={"name": "alerts"})
    assert r1.status_code == 201
    r2 = await client.post("/api/topics", json={"name": "alerts"})
    assert r2.status_code == 409
    assert "already" in r2.json()["detail"].lower()


@pytest.mark.asyncio
async def test_list_topics_empty(client):
    await _register(client)
    r = await client.get("/api/topics")
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_list_topics_returns_only_own(client):
    await _register(client)
    await client.post("/api/topics", json={"name": "alice-topic"})

    client.cookies.clear()
    await client.post(
        "/auth/register",
        json={"email": "bob@example.com", "password": "anotherpass"},
    )
    await client.post("/api/topics", json={"name": "bob-topic"})

    r = await client.get("/api/topics")
    items = r.json()
    assert len(items) == 1
    assert items[0]["name"] == "bob-topic"


@pytest.mark.asyncio
async def test_get_topic(client):
    await _register(client)
    await client.post("/api/topics", json={"name": "alerts"})
    r = await client.get("/api/topics/alerts")
    assert r.status_code == 200
    assert r.json()["name"] == "alerts"


@pytest.mark.asyncio
async def test_get_unknown_topic_404(client):
    await _register(client)
    r = await client.get("/api/topics/does-not-exist")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_get_other_users_topic_404(client):
    await _register(client)
    await client.post("/api/topics", json={"name": "alice-topic"})

    client.cookies.clear()
    await client.post(
        "/auth/register",
        json={"email": "bob@example.com", "password": "anotherpass"},
    )

    r = await client.get("/api/topics/alice-topic")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_patch_topic(client):
    await _register(client)
    await client.post(
        "/api/topics",
        json={"name": "alerts", "default_priority": 3, "retention_days": 7},
    )
    r = await client.patch(
        "/api/topics/alerts",
        json={"description": "updated", "retention_days": 14},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["description"] == "updated"
    assert body["retention_days"] == 14
    assert body["default_priority"] == 3  # unchanged


@pytest.mark.asyncio
async def test_patch_topic_priority_bounds(client):
    await _register(client)
    await client.post("/api/topics", json={"name": "alerts"})
    r = await client.patch("/api/topics/alerts", json={"default_priority": 9})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_patch_other_users_topic_404(client):
    await _register(client)
    await client.post("/api/topics", json={"name": "alice-topic"})

    client.cookies.clear()
    await client.post(
        "/auth/register",
        json={"email": "bob@example.com", "password": "anotherpass"},
    )

    r = await client.patch("/api/topics/alice-topic", json={"description": "hacked"})
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_delete_topic(client):
    await _register(client)
    await client.post("/api/topics", json={"name": "alerts"})
    r = await client.delete("/api/topics/alerts")
    assert r.status_code == 204
    r2 = await client.get("/api/topics")
    assert r2.json() == []


@pytest.mark.asyncio
async def test_delete_other_users_topic_404(client):
    await _register(client)
    await client.post("/api/topics", json={"name": "alice-topic"})

    client.cookies.clear()
    await client.post(
        "/auth/register",
        json={"email": "bob@example.com", "password": "anotherpass"},
    )

    r = await client.delete("/api/topics/alice-topic")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_topic_routes_require_auth(client):
    r = await client.get("/api/topics")
    assert r.status_code == 401
    r = await client.post("/api/topics", json={"name": "x"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_same_topic_name_different_users(client):
    """Per-user namespace: same topic name can exist for different users."""
    await _register(client, "alice@example.com")
    await client.post("/api/topics", json={"name": "shared-name"})

    client.cookies.clear()
    await client.post(
        "/auth/register",
        json={"email": "bob@example.com", "password": "anotherpass"},
    )
    r = await client.post("/api/topics", json={"name": "shared-name"})
    assert r.status_code == 201
