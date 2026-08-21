"""Rules CRUD tests."""
from __future__ import annotations

import pytest
from cryptography.fernet import Fernet


@pytest.fixture(autouse=True)
def _fernet_key(monkeypatch):
    monkeypatch.setenv("WEBHOOK_SECRET_KEY", Fernet.generate_key().decode())


async def _register(client) -> None:
    r = await client.post(
        "/auth/register",
        json={"email": "alice@example.com", "password": "verysecret"},
    )
    assert r.status_code == 201


@pytest.mark.asyncio
async def test_create_rule(client):
    await _register(client)
    r = await client.post(
        "/api/rules",
        json={"name": "all-events", "event_pattern": "*"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "all-events"
    assert body["event_pattern"] == "*"
    assert body["channel"] == "sse"
    assert body["enabled"] is True
    assert "id" in body


@pytest.mark.asyncio
async def test_list_rules_empty(client):
    await _register(client)
    r = await client.get("/api/rules")
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_list_rules_returns_only_own(client):
    await _register(client)
    await client.post("/api/rules", json={"name": "alice-rule", "event_pattern": "*"})

    client.cookies.clear()
    await client.post(
        "/auth/register",
        json={"email": "bob@example.com", "password": "anotherpass"},
    )
    await client.post("/api/rules", json={"name": "bob-rule", "event_pattern": "thread.*"})

    r = await client.get("/api/rules")
    items = r.json()
    assert len(items) == 1
    assert items[0]["name"] == "bob-rule"


@pytest.mark.asyncio
async def test_unsupported_channel_422(client):
    await _register(client)
    r = await client.post(
        "/api/rules",
        json={"name": "x", "event_pattern": "*", "channel": "email"},
    )
    assert r.status_code == 422
    assert "channel" in r.json()["detail"]


@pytest.mark.asyncio
async def test_empty_pattern_422(client):
    await _register(client)
    r = await client.post(
        "/api/rules",
        json={"name": "x", "event_pattern": ""},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_patch_rule_name(client):
    await _register(client)
    r = await client.post(
        "/api/rules", json={"name": "old-name", "event_pattern": "*"}
    )
    rid = r.json()["id"]

    r2 = await client.put(f"/api/rules/{rid}", json={"name": "new-name"})
    assert r2.status_code == 200
    assert r2.json()["name"] == "new-name"
    assert r2.json()["event_pattern"] == "*"  # unchanged


@pytest.mark.asyncio
async def test_patch_rule_disable(client):
    await _register(client)
    r = await client.post(
        "/api/rules", json={"name": "x", "event_pattern": "*", "enabled": True}
    )
    rid = r.json()["id"]

    r2 = await client.put(f"/api/rules/{rid}", json={"enabled": False})
    assert r2.status_code == 200
    assert r2.json()["enabled"] is False


@pytest.mark.asyncio
async def test_patch_rule_pattern_validates(client):
    await _register(client)
    r = await client.post(
        "/api/rules", json={"name": "x", "event_pattern": "*"}
    )
    rid = r.json()["id"]

    r2 = await client.put(f"/api/rules/{rid}", json={"event_pattern": "thread.*"})
    assert r2.status_code == 200
    assert r2.json()["event_pattern"] == "thread.*"


@pytest.mark.asyncio
async def test_patch_other_users_rule_404(client):
    await _register(client)
    r = await client.post(
        "/api/rules", json={"name": "alice", "event_pattern": "*"}
    )
    rid = r.json()["id"]

    client.cookies.clear()
    await client.post(
        "/auth/register",
        json={"email": "bob@example.com", "password": "anotherpass"},
    )

    r2 = await client.put(f"/api/rules/{rid}", json={"name": "hacked"})
    assert r2.status_code == 404


@pytest.mark.asyncio
async def test_delete_rule(client):
    await _register(client)
    r = await client.post(
        "/api/rules", json={"name": "x", "event_pattern": "*"}
    )
    rid = r.json()["id"]
    r2 = await client.delete(f"/api/rules/{rid}")
    assert r2.status_code == 204

    r3 = await client.get("/api/rules")
    assert r3.json() == []


@pytest.mark.asyncio
async def test_delete_other_users_rule_404(client):
    await _register(client)
    r = await client.post(
        "/api/rules", json={"name": "alice", "event_pattern": "*"}
    )
    rid = r.json()["id"]

    client.cookies.clear()
    await client.post(
        "/auth/register",
        json={"email": "bob@example.com", "password": "anotherpass"},
    )

    r2 = await client.delete(f"/api/rules/{rid}")
    assert r2.status_code == 404


@pytest.mark.asyncio
async def test_get_with_invalid_uuid_404(client):
    await _register(client)
    r = await client.put("/api/rules/not-a-uuid", json={"name": "x"})
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_patch_with_empty_pattern_422(client):
    """Pydantic min_length=1 catches empty event_pattern on PATCH too."""
    await _register(client)
    r = await client.post(
        "/api/rules", json={"name": "x", "event_pattern": "*"}
    )
    rid = r.json()["id"]
    r2 = await client.put(f"/api/rules/{rid}", json={"event_pattern": ""})
    assert r2.status_code == 422


@pytest.mark.asyncio
async def test_create_requires_auth(client):
    r = await client.post("/api/rules", json={"name": "x", "event_pattern": "*"})
    assert r.status_code == 401