"""Auth endpoint tests: register, login, me, logout, password reset."""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_register_then_me(client):
    r = await client.post(
        "/auth/register",
        json={"email": "alice@example.com", "password": "verysecret"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["email"] == "alice@example.com"
    assert "id" in body
    # Cookie should have been set.
    assert "notifier_session" in r.cookies

    r2 = await client.get("/auth/me")
    assert r2.status_code == 200
    assert r2.json()["email"] == "alice@example.com"


@pytest.mark.asyncio
async def test_register_duplicate_409(client):
    await client.post(
        "/auth/register",
        json={"email": "alice@example.com", "password": "verysecret"},
    )
    r = await client.post(
        "/auth/register",
        json={"email": "alice@example.com", "password": "anotherone"},
    )
    assert r.status_code == 409
    assert "already" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_register_password_too_short_422(client):
    r = await client.post(
        "/auth/register",
        json={"email": "alice@example.com", "password": "short"},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_register_invalid_email_422(client):
    r = await client.post(
        "/auth/register",
        json={"email": "not-an-email", "password": "verysecret"},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_login_wrong_password_401(client):
    await client.post(
        "/auth/register",
        json={"email": "alice@example.com", "password": "verysecret"},
    )
    r = await client.post(
        "/auth/login",
        json={"email": "alice@example.com", "password": "wrongpass"},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_login_unknown_email_401(client):
    r = await client.post(
        "/auth/login",
        json={"email": "ghost@example.com", "password": "anyvaluehere"},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_login_success_sets_cookie(client):
    await client.post(
        "/auth/register",
        json={"email": "alice@example.com", "password": "verysecret"},
    )
    # Drop the cookie to simulate a fresh device.
    client.cookies.clear()
    r = await client.post(
        "/auth/login",
        json={"email": "alice@example.com", "password": "verysecret"},
    )
    assert r.status_code == 200
    assert "notifier_session" in r.cookies


@pytest.mark.asyncio
async def test_me_without_cookie_401(client):
    r = await client.get("/auth/me")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_me_with_garbage_cookie_401(client):
    client.cookies.set("notifier_session", "garbage.token.value")
    r = await client.get("/auth/me")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_logout_clears_cookie(client):
    r = await client.post(
        "/auth/register",
        json={"email": "alice@example.com", "password": "verysecret"},
    )
    assert "notifier_session" in r.cookies
    r2 = await client.post("/auth/logout")
    assert r2.status_code == 204
    # httpx sees the Set-Cookie with Max-Age=0 and removes it from the jar.
    assert "notifier_session" not in client.cookies
    # And /me is now unauthenticated.
    r3 = await client.get("/auth/me")
    assert r3.status_code == 401


@pytest.mark.asyncio
async def test_reset_request_unknown_email_returns_202(client, capsys):
    """No email enumeration: unknown email still returns 202."""
    r = await client.post(
        "/auth/reset-password", json={"email": "ghost@example.com"}
    )
    assert r.status_code == 202


@pytest.mark.asyncio
async def test_reset_request_prints_url(client, capsys):
    """Known email → reset URL printed to stdout for operator pickup."""
    await client.post(
        "/auth/register",
        json={"email": "alice@example.com", "password": "verysecret"},
    )
    capsys.readouterr()  # clear register output
    r = await client.post(
        "/auth/reset-password", json={"email": "alice@example.com"}
    )
    assert r.status_code == 202
    captured = capsys.readouterr()
    assert "[reset-password]" in captured.out
    assert "alice@example.com" in captured.out
    assert "/reset?token=" in captured.out


@pytest.mark.asyncio
async def test_reset_confirm_round_trip(client, capsys):
    """Full flow: register → reset request → confirm with captured token → login."""
    await client.post(
        "/auth/register",
        json={"email": "alice@example.com", "password": "oldpassword"},
    )
    capsys.readouterr()
    await client.post(
        "/auth/reset-password", json={"email": "alice@example.com"}
    )
    out = capsys.readouterr().out
    # Parse token out of the URL: ".../reset?token=XXXXX"
    token = out.split("/reset?token=")[1].split()[0].strip()

    r = await client.post(
        "/auth/reset-password/confirm",
        json={"token": token, "new_password": "newpassword"},
    )
    assert r.status_code == 204

    # Now login with the new password.
    client.cookies.clear()
    r2 = await client.post(
        "/auth/login",
        json={"email": "alice@example.com", "password": "newpassword"},
    )
    assert r2.status_code == 200

    # Old password should no longer work.
    client.cookies.clear()
    r3 = await client.post(
        "/auth/login",
        json={"email": "alice@example.com", "password": "oldpassword"},
    )
    assert r3.status_code == 401


@pytest.mark.asyncio
async def test_reset_confirm_token_reuse_rejected(client, capsys):
    """Reset tokens are one-shot — second use must fail."""
    await client.post(
        "/auth/register",
        json={"email": "alice@example.com", "password": "oldpassword"},
    )
    capsys.readouterr()
    await client.post(
        "/auth/reset-password", json={"email": "alice@example.com"}
    )
    out = capsys.readouterr().out
    token = out.split("/reset?token=")[1].split()[0].strip()

    r1 = await client.post(
        "/auth/reset-password/confirm",
        json={"token": token, "new_password": "newpassword1"},
    )
    assert r1.status_code == 204
    r2 = await client.post(
        "/auth/reset-password/confirm",
        json={"token": token, "new_password": "newpassword2"},
    )
    assert r2.status_code == 400


@pytest.mark.asyncio
async def test_reset_confirm_invalid_token_400(client):
    r = await client.post(
        "/auth/reset-password/confirm",
        json={"token": "definitely-not-a-real-token-32chars-long", "new_password": "newpassword"},
    )
    assert r.status_code == 400
