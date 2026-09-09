"""Sound CRUD + topic-attachment tests."""
from __future__ import annotations

import pytest


async def _register(client, email: str = "alice@example.com") -> None:
    r = await client.post(
        "/auth/register",
        json={"email": email, "password": "verysecret"},
    )
    assert r.status_code == 201, r.text


async def _create_topic(client, name: str) -> None:
    r = await client.post("/api/topics", json={"name": name})
    assert r.status_code == 201, r.text


# ── Sound CRUD ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_sound_round_trip(client):
    await _register(client)
    r = await client.post(
        "/api/sounds",
        json={"name": "ping", "url": "https://example.com/ping.mp3"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["name"] == "ping"
    assert body["url"] == "https://example.com/ping.mp3"
    assert "id" in body
    assert "created_at" in body


@pytest.mark.asyncio
async def test_list_sounds_returns_only_own(client):
    await _register(client, "alice@example.com")
    await client.post(
        "/api/sounds",
        json={"name": "alice-sound", "url": "https://example.com/a.mp3"},
    )

    client.cookies.clear()
    await _register(client, "bob@example.com")
    await client.post(
        "/api/sounds",
        json={"name": "bob-sound", "url": "https://example.com/b.mp3"},
    )

    r = await client.get("/api/sounds")
    items = r.json()
    assert len(items) == 1
    assert items[0]["name"] == "bob-sound"


@pytest.mark.asyncio
async def test_patch_sound(client):
    await _register(client)
    r = await client.post(
        "/api/sounds",
        json={"name": "ping", "url": "https://example.com/old.mp3"},
    )
    sid = r.json()["id"]
    r2 = await client.patch(
        f"/api/sounds/{sid}",
        json={"url": "https://example.com/new.mp3"},
    )
    assert r2.status_code == 200
    assert r2.json()["url"] == "https://example.com/new.mp3"
    assert r2.json()["name"] == "ping"


@pytest.mark.asyncio
async def test_delete_sound_204(client):
    await _register(client)
    r = await client.post(
        "/api/sounds",
        json={"name": "ping", "url": "https://example.com/ping.mp3"},
    )
    sid = r.json()["id"]
    r2 = await client.delete(f"/api/sounds/{sid}")
    assert r2.status_code == 204
    assert (await client.get("/api/sounds")).json() == []


# ── Per-user isolation (404, not 403, matches topics convention) ──


@pytest.mark.asyncio
async def test_get_other_users_sound_404(client):
    await _register(client, "alice@example.com")
    r = await client.post(
        "/api/sounds",
        json={"name": "alice-sound", "url": "https://example.com/a.mp3"},
    )
    sid = r.json()["id"]

    client.cookies.clear()
    await _register(client, "bob@example.com")

    r2 = await client.get(f"/api/sounds/{sid}")
    assert r2.status_code == 404


@pytest.mark.asyncio
async def test_patch_other_users_sound_404(client):
    await _register(client, "alice@example.com")
    r = await client.post(
        "/api/sounds",
        json={"name": "alice-sound", "url": "https://example.com/a.mp3"},
    )
    sid = r.json()["id"]

    client.cookies.clear()
    await _register(client, "bob@example.com")

    r2 = await client.patch(
        f"/api/sounds/{sid}",
        json={"name": "hacked"},
    )
    assert r2.status_code == 404


@pytest.mark.asyncio
async def test_delete_other_users_sound_404(client):
    await _register(client, "alice@example.com")
    r = await client.post(
        "/api/sounds",
        json={"name": "alice-sound", "url": "https://example.com/a.mp3"},
    )
    sid = r.json()["id"]

    client.cookies.clear()
    await _register(client, "bob@example.com")

    r2 = await client.delete(f"/api/sounds/{sid}")
    assert r2.status_code == 404


# ── Topic attachment ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_topic_with_sound_id_attaches(client):
    await _register(client)
    r = await client.post(
        "/api/sounds",
        json={"name": "ping", "url": "https://example.com/ping.mp3"},
    )
    sid = r.json()["id"]

    r2 = await client.post(
        "/api/topics",
        json={"name": "alerts", "sound_id": sid},
    )
    assert r2.status_code == 201
    body = r2.json()
    assert body["sound"] is not None
    assert body["sound"]["id"] == sid
    assert body["sound"]["url"] == "https://example.com/ping.mp3"


@pytest.mark.asyncio
async def test_attach_other_users_sound_to_topic_404(client):
    await _register(client, "alice@example.com")
    r = await client.post(
        "/api/sounds",
        json={"name": "alice-sound", "url": "https://example.com/a.mp3"},
    )
    alice_sid = r.json()["id"]

    client.cookies.clear()
    await _register(client, "bob@example.com")
    r2 = await client.post(
        "/api/topics",
        json={"name": "bob-topic", "sound_id": alice_sid},
    )
    assert r2.status_code == 404


@pytest.mark.asyncio
async def test_patch_topic_attaches_sound(client):
    await _register(client)
    r = await client.post(
        "/api/sounds",
        json={"name": "ping", "url": "https://example.com/ping.mp3"},
    )
    sid = r.json()["id"]
    await _create_topic(client, "alerts")

    r2 = await client.patch(
        "/api/topics/alerts",
        json={"sound_id": sid},
    )
    assert r2.status_code == 200
    assert r2.json()["sound"]["id"] == sid


@pytest.mark.asyncio
async def test_patch_topic_explicit_null_unsets_sound(client):
    """model_fields_set distinguishes "absent" from "explicit null" — without
    it the user could never detach a sound via PATCH.
    """
    await _register(client)
    r = await client.post(
        "/api/sounds",
        json={"name": "ping", "url": "https://example.com/ping.mp3"},
    )
    sid = r.json()["id"]
    await client.post(
        "/api/topics",
        json={"name": "alerts", "sound_id": sid},
    )
    # Verify it's attached.
    assert (await client.get("/api/topics/alerts")).json()["sound"]["id"] == sid

    # Explicit null — must detach.
    r2 = await client.patch(
        "/api/topics/alerts",
        json={"sound_id": None},
    )
    assert r2.status_code == 200
    assert r2.json()["sound"] is None


@pytest.mark.asyncio
async def test_patch_topic_omitted_sound_id_does_not_change(client):
    """PATCH without sound_id in body must leave existing sound untouched."""
    await _register(client)
    r = await client.post(
        "/api/sounds",
        json={"name": "ping", "url": "https://example.com/ping.mp3"},
    )
    sid = r.json()["id"]
    await client.post(
        "/api/topics",
        json={"name": "alerts", "sound_id": sid},
    )

    # PATCH unrelated fields — sound must stay attached.
    r2 = await client.patch(
        "/api/topics/alerts",
        json={"description": "updated"},
    )
    assert r2.status_code == 200
    assert r2.json()["sound"]["id"] == sid


@pytest.mark.asyncio
async def test_delete_sound_leaves_topic_with_null_sound(client):
    """ON DELETE SET NULL: deleting a sound detaches it from any topic that
    referenced it. Topic itself must survive.
    """
    await _register(client)
    r = await client.post(
        "/api/sounds",
        json={"name": "ping", "url": "https://example.com/ping.mp3"},
    )
    sid = r.json()["id"]
    await client.post(
        "/api/topics",
        json={"name": "alerts", "sound_id": sid},
    )

    r2 = await client.delete(f"/api/sounds/{sid}")
    assert r2.status_code == 204

    # Topic survives with sound detached.
    r3 = await client.get("/api/topics/alerts")
    assert r3.status_code == 200
    assert r3.json()["sound"] is None
