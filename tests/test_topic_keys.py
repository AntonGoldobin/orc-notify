"""Topic key CRUD tests."""
from __future__ import annotations

import pytest
from cryptography.fernet import Fernet


@pytest.fixture(autouse=True)
def _fernet_key(monkeypatch):
    monkeypatch.setenv("WEBHOOK_SECRET_KEY", Fernet.generate_key().decode())


async def _register_and_create_topic(
    client, email: str = "alice@example.com", topic_name: str = "alerts"
) -> str:
    r = await client.post(
        "/auth/register",
        json={"email": email, "password": "verysecret"},
    )
    assert r.status_code == 201
    r = await client.post("/api/topics", json={"name": topic_name})
    assert r.status_code == 201
    return r.json()["id"]


@pytest.mark.asyncio
async def test_create_key_returns_secret_once(client):
    await _register_and_create_topic(client)
    r = await client.post(
        "/api/topics/alerts/keys", json={"name": "publisher"}
    )
    assert r.status_code == 201
    body = r.json()
    assert "secret" in body
    assert len(body["secret"]) >= 40
    assert body["name"] == "publisher"
    assert body["scopes"] == "publish,read"

    # GET must NOT include secret.
    r2 = await client.get("/api/topics/alerts/keys")
    assert r2.status_code == 200
    keys = r2.json()
    assert len(keys) == 1
    assert "secret" not in keys[0]


@pytest.mark.asyncio
async def test_create_key_with_explicit_scopes(client):
    await _register_and_create_topic(client)
    r = await client.post(
        "/api/topics/alerts/keys",
        json={"name": "subscriber", "scopes": "read"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["scopes"] == "read"


@pytest.mark.asyncio
async def test_create_key_invalid_scope_422(client):
    await _register_and_create_topic(client)
    r = await client.post(
        "/api/topics/alerts/keys",
        json={"name": "x", "scopes": "admin"},
    )
    assert r.status_code == 422
    assert "scope" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_create_key_no_scopes_422(client):
    await _register_and_create_topic(client)
    r = await client.post(
        "/api/topics/alerts/keys",
        json={"name": "x", "scopes": ""},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_create_key_unknown_topic_404(client):
    await client.post(
        "/auth/register",
        json={"email": "alice@example.com", "password": "verysecret"},
    )
    r = await client.post(
        "/api/topics/no-such-topic/keys", json={"name": "x"}
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_list_keys(client):
    await _register_and_create_topic(client)
    await client.post("/api/topics/alerts/keys", json={"name": "k1"})
    await client.post("/api/topics/alerts/keys", json={"name": "k2"})
    r = await client.get("/api/topics/alerts/keys")
    assert r.status_code == 200
    keys = r.json()
    assert len(keys) == 2
    names = {k["name"] for k in keys}
    assert names == {"k1", "k2"}


@pytest.mark.asyncio
async def test_list_keys_only_own_topic(client):
    """Alice's topic + Bob's topic → Alice sees only her keys."""
    await _register_and_create_topic(client, "alice@example.com", "alice-topic")
    await client.post("/api/topics/alice-topic/keys", json={"name": "alice-key"})

    client.cookies.clear()
    await client.post(
        "/auth/register",
        json={"email": "bob@example.com", "password": "anotherpass"},
    )
    await client.post("/api/topics", json={"name": "bob-topic"})

    # Bob sees no keys for his (empty) topic.
    r = await client.get("/api/topics/bob-topic/keys")
    assert r.status_code == 200
    assert r.json() == []

    # Bob cannot list Alice's keys.
    r2 = await client.get("/api/topics/alice-topic/keys")
    assert r2.status_code == 404


@pytest.mark.asyncio
async def test_patch_key_rotates_secret(client):
    await _register_and_create_topic(client)
    r1 = await client.post(
        "/api/topics/alerts/keys", json={"name": "publisher"}
    )
    kid = r1.json()["id"]
    old_secret = r1.json()["secret"]

    r2 = await client.patch(f"/api/topics/alerts/keys/{kid}", json={"name": "renamed"})
    assert r2.status_code == 200
    body = r2.json()
    assert body["name"] == "renamed"
    assert "secret" in body
    assert body["secret"] != old_secret  # rotated


@pytest.mark.asyncio
async def test_patch_key_change_scopes(client):
    await _register_and_create_topic(client)
    r = await client.post(
        "/api/topics/alerts/keys",
        json={"name": "k", "scopes": "publish,read"},
    )
    kid = r.json()["id"]

    r2 = await client.patch(f"/api/topics/alerts/keys/{kid}", json={"scopes": "read"})
    assert r2.status_code == 200
    assert r2.json()["scopes"] == "read"


@pytest.mark.asyncio
async def test_patch_other_users_key_404(client):
    await _register_and_create_topic(client, "alice@example.com", "alice-topic")
    r = await client.post(
        "/api/topics/alice-topic/keys", json={"name": "alice-key"}
    )
    kid = r.json()["id"]

    client.cookies.clear()
    await client.post(
        "/auth/register",
        json={"email": "bob@example.com", "password": "anotherpass"},
    )

    r2 = await client.patch(f"/api/topics/alice-topic/keys/{kid}", json={"name": "x"})
    assert r2.status_code == 404


@pytest.mark.asyncio
async def test_patch_invalid_key_id_404(client):
    await _register_and_create_topic(client)
    r = await client.patch(
        "/api/topics/alerts/keys/not-a-uuid", json={"name": "x"}
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_delete_key(client):
    await _register_and_create_topic(client)
    r = await client.post("/api/topics/alerts/keys", json={"name": "k"})
    kid = r.json()["id"]

    r2 = await client.delete(f"/api/topics/alerts/keys/{kid}")
    assert r2.status_code == 204

    r3 = await client.get("/api/topics/alerts/keys")
    assert r3.json() == []


@pytest.mark.asyncio
async def test_delete_other_users_key_404(client):
    await _register_and_create_topic(client, "alice@example.com", "alice-topic")
    r = await client.post(
        "/api/topics/alice-topic/keys", json={"name": "alice-key"}
    )
    kid = r.json()["id"]

    client.cookies.clear()
    await client.post(
        "/auth/register",
        json={"email": "bob@example.com", "password": "anotherpass"},
    )

    r2 = await client.delete(f"/api/topics/alice-topic/keys/{kid}")
    assert r2.status_code == 404


@pytest.mark.asyncio
async def test_delete_unknown_key_404(client):
    await _register_and_create_topic(client)
    r = await client.delete("/api/topics/alerts/keys/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_create_key_no_webhook_key_503(client, monkeypatch):
    """Empty WEBHOOK_SECRET_KEY → 503 on key creation."""
    monkeypatch.setenv("WEBHOOK_SECRET_KEY", "")
    from app.config import get_settings
    from app.secrets import _fernet

    get_settings.cache_clear()
    _fernet.cache_clear()

    await _register_and_create_topic(client)
    r = await client.post(
        "/api/topics/alerts/keys", json={"name": "no-key"}
    )
    assert r.status_code == 503
