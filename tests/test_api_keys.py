"""API key management tests: list/create/delete/rotate + public health."""
from __future__ import annotations

import pytest
from cryptography.fernet import Fernet


@pytest.fixture(autouse=True)
def _fernet_key(monkeypatch):
    """Set WEBHOOK_SECRET_KEY before each test (autouse on this module)."""
    monkeypatch.setenv("WEBHOOK_SECRET_KEY", Fernet.generate_key().decode())


async def _register(client) -> dict:
    r = await client.post(
        "/auth/register",
        json={"email": "alice@example.com", "password": "verysecret"},
    )
    assert r.status_code == 201
    return r.json()


@pytest.mark.asyncio
async def test_create_returns_secret_once(client):
    await _register(client)
    r = await client.post(
        "/api/keys", json={"name": "orchestrator"}
    )
    assert r.status_code == 201
    body = r.json()
    assert "webhook_secret" in body
    assert len(body["webhook_secret"]) >= 40
    assert body["name"] == "orchestrator"
    assert "agent_id" in body and len(body["agent_id"]) > 0

    # GET must NOT include webhook_secret.
    r2 = await client.get("/api/keys")
    assert r2.status_code == 200
    agents = r2.json()
    assert len(agents) == 1
    assert "webhook_secret" not in agents[0]
    assert agents[0]["agent_id"] == body["agent_id"]


@pytest.mark.asyncio
async def test_create_uses_explicit_agent_id(client):
    await _register(client)
    r = await client.post(
        "/api/keys", json={"name": "ci-runner", "agent_id": "ci-prod"}
    )
    assert r.status_code == 201
    assert r.json()["agent_id"] == "ci-prod"


@pytest.mark.asyncio
async def test_create_collision_returns_409(client):
    await _register(client)
    r1 = await client.post(
        "/api/keys", json={"name": "first", "agent_id": "shared"}
    )
    assert r1.status_code == 201
    r2 = await client.post(
        "/api/keys", json={"name": "second", "agent_id": "shared"}
    )
    assert r2.status_code == 409


@pytest.mark.asyncio
async def test_create_auto_generates_unique_agent_ids(client):
    await _register(client)
    ids = set()
    for i in range(3):
        r = await client.post("/api/keys", json={"name": f"agent-{i}"})
        assert r.status_code == 201
        ids.add(r.json()["agent_id"])
    assert len(ids) == 3  # no collisions


@pytest.mark.asyncio
async def test_list_only_returns_own_agents(client):
    """Two users, two cookies — each sees only their own."""
    await _register(client)
    await client.post("/api/keys", json={"name": "alice-agent"})

    client.cookies.clear()
    await client.post(
        "/auth/register",
        json={"email": "bob@example.com", "password": "anotherpass"},
    )
    await client.post("/api/keys", json={"name": "bob-agent"})

    r = await client.get("/api/keys")
    assert r.status_code == 200
    agents = r.json()
    assert len(agents) == 1
    assert agents[0]["name"] == "bob-agent"


@pytest.mark.asyncio
async def test_delete_agent(client):
    await _register(client)
    r = await client.post("/api/keys", json={"name": "to-delete"})
    aid = r.json()["agent_id"]

    r2 = await client.delete(f"/api/keys/{aid}")
    assert r2.status_code == 204

    r3 = await client.get("/api/keys")
    assert r3.status_code == 200
    assert r3.json() == []


@pytest.mark.asyncio
async def test_delete_other_users_agent_404(client):
    await _register(client)
    r = await client.post("/api/keys", json={"name": "alice-agent"})
    aid = r.json()["agent_id"]

    client.cookies.clear()
    await client.post(
        "/auth/register",
        json={"email": "bob@example.com", "password": "anotherpass"},
    )

    r2 = await client.delete(f"/api/keys/{aid}")
    assert r2.status_code == 404


@pytest.mark.asyncio
async def test_delete_nonexistent_agent_404(client):
    await _register(client)
    r = await client.delete("/api/keys/does-not-exist")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_rotate_returns_new_secret_once(client):
    await _register(client)
    r1 = await client.post("/api/keys", json={"name": "rotate-me"})
    aid = r1.json()["agent_id"]
    old_secret = r1.json()["webhook_secret"]

    r2 = await client.post(f"/api/keys/{aid}/rotate-secret")
    assert r2.status_code == 200
    new_secret = r2.json()["webhook_secret"]
    assert new_secret != old_secret
    assert len(new_secret) >= 40

    r3 = await client.get("/api/keys")
    assert "webhook_secret" not in r3.json()[0]


@pytest.mark.asyncio
async def test_rotate_other_users_agent_404(client):
    await _register(client)
    r = await client.post("/api/keys", json={"name": "alice-agent"})
    aid = r.json()["agent_id"]

    client.cookies.clear()
    await client.post(
        "/auth/register",
        json={"email": "bob@example.com", "password": "anotherpass"},
    )

    r2 = await client.post(f"/api/keys/{aid}/rotate-secret")
    assert r2.status_code == 404


@pytest.mark.asyncio
async def test_health_unknown_agent_404(client):
    r = await client.get("/v1/agents/no-such-agent/health")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_health_no_auth_required(client):
    """Health endpoint is public — no cookie needed."""
    # No registration here.
    # We have to create an agent through another path... but registration
    # creates a user and we need a user to create an agent. So register
    # via auth, then drop the cookie, then probe health.
    await _register(client)
    r = await client.post("/api/keys", json={"name": "public-health"})
    aid = r.json()["agent_id"]

    client.cookies.clear()
    r2 = await client.get(f"/v1/agents/{aid}/health")
    assert r2.status_code == 200
    body = r2.json()
    assert body["agent_id"] == aid
    assert body["status"] == "ok"
    assert body["last_event_at"] is None


@pytest.mark.asyncio
async def test_create_without_webhook_secret_key_503(client, monkeypatch):
    """Empty WEBHOOK_SECRET_KEY → 503 on agent creation."""
    monkeypatch.setenv("WEBHOOK_SECRET_KEY", "")
    # Both caches must be cleared — Settings reads env at first call, then
    # _fernet() caches the Fernet instance built from those settings.
    from app.config import get_settings
    from app.secrets import _fernet
    get_settings.cache_clear()
    _fernet.cache_clear()

    await _register(client)
    r = await client.post("/api/keys", json={"name": "no-key"})
    assert r.status_code == 503
    assert "WEBHOOK_SECRET_KEY" in r.json()["detail"]