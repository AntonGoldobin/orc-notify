"""UI smoke tests — render pages, create/rotate/delete via form posts."""
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
async def test_root_redirects_to_login_when_anon(client):
    r = await client.get("/", follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == "/login"


@pytest.mark.asyncio
async def test_root_redirects_to_dashboard_when_authed(client):
    await _register(client)
    r = await client.get("/", follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == "/dashboard"


@pytest.mark.asyncio
async def test_login_page_renders(client):
    r = await client.get("/login")
    assert r.status_code == 200
    assert "Sign in" in r.text


@pytest.mark.asyncio
async def test_register_page_renders(client):
    r = await client.get("/register")
    assert r.status_code == 200
    assert "Create account" in r.text


@pytest.mark.asyncio
async def test_dashboard_requires_auth(client):
    r = await client.get("/dashboard", follow_redirects=False)
    # FastAPI returns 401 for missing cookie on a dep-protected endpoint
    # (we don't issue a redirect for HTML — the user agent handles it).
    assert r.status_code in (302, 401)


@pytest.mark.asyncio
async def test_dashboard_renders_empty_feed(client):
    await _register(client)
    r = await client.get("/dashboard")
    assert r.status_code == 200
    assert "Live feed" in r.text
    assert "No events yet" in r.text


@pytest.mark.asyncio
async def test_keys_page_renders_and_lists_agents(client):
    await _register(client)
    r = await client.get("/keys")
    assert r.status_code == 200
    assert "API keys" in r.text
    assert "No agents yet" in r.text


@pytest.mark.asyncio
async def test_create_agent_via_form(client):
    await _register(client)
    r = await client.post(
        "/keys/create",
        data={"name": "form-agent"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers["location"] == "/keys"

    # Page now lists the agent.
    r2 = await client.get("/keys")
    assert "form-agent" in r2.text


@pytest.mark.asyncio
async def test_rotate_secret_via_form(client):
    await _register(client)
    await client.post("/keys/create", data={"name": "rot"}, follow_redirects=False)
    # Find the agent_id
    import re
    page = (await client.get("/keys")).text
    m = re.search(r"<code>(rot-[a-f0-9]+)</code>", page)
    assert m, page
    aid = m.group(1)

    r = await client.post(f"/keys/{aid}/rotate", follow_redirects=False)
    assert r.status_code == 303


@pytest.mark.asyncio
async def test_delete_agent_via_form(client):
    await _register(client)
    await client.post("/keys/create", data={"name": "del"}, follow_redirects=False)
    import re
    page = (await client.get("/keys")).text
    m = re.search(r"<code>(del-[a-f0-9]+)</code>", page)
    aid = m.group(1)

    r = await client.post(f"/keys/{aid}/delete", follow_redirects=False)
    assert r.status_code == 303
    page2 = (await client.get("/keys")).text
    assert aid not in page2


@pytest.mark.asyncio
async def test_rules_page_renders(client):
    await _register(client)
    r = await client.get("/rules")
    assert r.status_code == 200
    assert "Rules" in r.text
    assert "No rules" in r.text


@pytest.mark.asyncio
async def test_create_rule_via_form(client):
    await _register(client)
    r = await client.post(
        "/rules/create",
        data={"name": "all-thread", "event_pattern": "thread.*", "enabled": "true"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    page = (await client.get("/rules")).text
    assert "all-thread" in page
    assert "thread.*" in page


@pytest.mark.asyncio
async def test_create_rule_invalid_pattern_via_form(client):
    await _register(client)
    r = await client.post(
        "/rules/create",
        data={"name": "x", "event_pattern": "[unclosed", "enabled": "true"},
        follow_redirects=False,
    )
    # fnmatch.translate doesn't actually raise on this input — so we expect 303.
    # The point of this test is that the form does not 500.
    assert r.status_code == 303


@pytest.mark.asyncio
async def test_delete_rule_via_form(client):
    await _register(client)
    r = await client.post(
        "/rules/create",
        data={"name": "doomed", "event_pattern": "*", "enabled": "true"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    page = (await client.get("/rules")).text
    # Rule ID is a UUID
    import re
    m = re.search(r"/rules/([0-9a-f-]{36})/delete", page)
    assert m, page
    rid = m.group(1)

    r2 = await client.post(f"/rules/{rid}/delete", follow_redirects=False)
    assert r2.status_code == 303


@pytest.mark.asyncio
async def test_settings_page_renders(client):
    await _register(client)
    r = await client.get("/settings")
    assert r.status_code == 200
    assert "alice@example.com" in r.text


@pytest.mark.asyncio
async def test_change_password_via_form(client):
    await _register(client)
    r = await client.post(
        "/settings/password",
        data={"current_password": "verysecret", "new_password": "newsecret"},
        follow_redirects=False,
    )
    assert r.status_code == 303

    # Old password no longer works
    client.cookies.clear()
    r2 = await client.post(
        "/auth/login",
        json={"email": "alice@example.com", "password": "verysecret"},
    )
    assert r2.status_code == 401

    # New password does
    r3 = await client.post(
        "/auth/login",
        json={"email": "alice@example.com", "password": "newsecret"},
    )
    assert r3.status_code == 200


@pytest.mark.asyncio
async def test_change_password_wrong_current(client):
    await _register(client)
    r = await client.post(
        "/settings/password",
        data={"current_password": "wrong", "new_password": "newsecret"},
        follow_redirects=False,
    )
    assert r.status_code == 303


@pytest.mark.asyncio
async def test_reset_page_renders(client):
    r = await client.get("/reset?token=fake-but-long-enough")
    assert r.status_code == 200
    assert "Reset password" in r.text


@pytest.mark.asyncio
async def test_reset_form_invalid_token_redirects_back(client):
    r = await client.post(
        "/reset",
        data={"token": "definitely-not-a-real-token-32chars", "new_password": "newpass"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers["location"] == "/reset"