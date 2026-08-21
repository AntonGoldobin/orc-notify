"""UI router — server-rendered Jinja2 pages with HTMX progressive enhancement.

Page routing:
  GET  /              redirect to /dashboard if logged in, else /login
  GET  /login         login form (HTMX posts to /auth/login)
  GET  /register      registration form (HTMX posts to /auth/register)
  GET  /dashboard     feed: last 50 notifications + EventSource live tail
  GET  /keys          API keys list + create form + rotate/delete
  GET  /rules         rules list + create form + edit/delete
  GET  /settings      logout + change password form
  GET  /reset         reset-password form (?token=...)

All write paths POST to existing API endpoints; UI just renders. To keep the
form-to-API mapping 1:1, we accept JSON bodies on POST too.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_db
from app.deps import get_current_user
from app.models import Agent, Rule, User
from app.secrets import SecretKeyError, encrypt_secret
from app.services.events import get_user_notifications
from app.services.pubsub import get_pubsub
from app.security import hash_password

router = APIRouter(tags=["ui"])

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def _fmt_dt(value: datetime | None) -> str:
    if value is None:
        return "—"
    return value.strftime("%Y-%m-%d %H:%M:%S UTC")


templates.env.filters["fmt_dt"] = _fmt_dt


def _is_htmx(request: Request) -> bool:
    return request.headers.get("hx-request") == "true"


@router.get("/", response_class=HTMLResponse)
async def root(request: Request) -> RedirectResponse:
    if request.cookies.get(get_settings().cookie_name):
        return RedirectResponse("/dashboard", status_code=302)
    return RedirectResponse("/login", status_code=302)


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "login.html")


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "register.html")


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    rows = await get_user_notifications(db, user.id, limit=50)
    feed = [
        {
            "notification_id": n.id,
            "event_id": e.id,
            "event_name": e.event,
            "thread_id": e.thread_id,
            "project_name": e.project_name,
            "summary": e.summary,
            "status": e.status,
            "pr_url": e.pr_url,
            "delivered_at": n.delivered_at,
            "rule_name": r.name if r else None,
        }
        for n, e, r in rows
    ]
    return templates.TemplateResponse(
        request, "dashboard.html", {"user": user, "feed": feed}
    )


@router.get("/keys", response_class=HTMLResponse)
async def keys_page(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    rows = await db.execute(
        select(Agent).where(Agent.user_id == user.id).order_by(Agent.created_at.desc())
    )
    agents = rows.scalars().all()
    return templates.TemplateResponse(
        request, "keys.html", {"user": user, "agents": agents}
    )


@router.post("/keys/create")
async def keys_create(
    request: Request,
    name: str = Form(),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    if not name.strip():
        raise HTTPException(status_code=422, detail="name required")
    import secrets as _secrets

    raw = _secrets.token_urlsafe(32)
    try:
        encrypted = encrypt_secret(raw)
    except SecretKeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        )
    agent = Agent(user_id=user.id, name=name, webhook_secret_ct=encrypted)
    # Auto-generate agent_id
    from app.routers.api_keys import _slug

    agent.agent_id = f"{_slug(name)}-{_secrets.token_hex(3)}"
    db.add(agent)
    await db.commit()
    request.session["flash"] = f"New agent created. webhook_secret={raw} — copy now (shown once)."
    return RedirectResponse("/keys", status_code=303)


@router.post("/keys/{agent_id}/rotate")
async def keys_rotate(
    agent_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    import secrets as _secrets

    row = await db.execute(
        select(Agent).where(Agent.user_id == user.id, Agent.agent_id == agent_id)
    )
    agent = row.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    raw = _secrets.token_urlsafe(32)
    try:
        agent.webhook_secret_ct = encrypt_secret(raw)
    except SecretKeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        )
    await db.commit()
    request.session["flash"] = f"New secret for {agent_id}: {raw} — copy now (shown once)."
    return RedirectResponse("/keys", status_code=303)


@router.post("/keys/{agent_id}/delete")
async def keys_delete(
    agent_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    row = await db.execute(
        select(Agent).where(Agent.user_id == user.id, Agent.agent_id == agent_id)
    )
    agent = row.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    await db.delete(agent)
    await db.commit()
    return RedirectResponse("/keys", status_code=303)


@router.get("/rules", response_class=HTMLResponse)
async def rules_page(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    rows = await db.execute(
        select(Rule).where(Rule.user_id == user.id).order_by(Rule.created_at.desc())
    )
    rules = rows.scalars().all()
    return templates.TemplateResponse(
        request, "rules.html", {"user": user, "rules": rules}
    )


@router.post("/rules/create")
async def rules_create(
    request: Request,
    name: str = Form(),
    event_pattern: str = Form(),
    enabled: str = Form(default="true"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    from fnmatch import translate as _translate

    try:
        _translate(event_pattern)
    except (ValueError, TypeError) as exc:
        request.session["flash"] = f"Invalid pattern: {exc}"
        return RedirectResponse("/rules", status_code=303)
    rule = Rule(
        user_id=user.id,
        name=name,
        event_pattern=event_pattern,
        channel="sse",
        enabled=enabled.lower() in ("true", "on", "1"),
    )
    db.add(rule)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        request.session["flash"] = "Could not create rule."
    return RedirectResponse("/rules", status_code=303)


@router.post("/rules/{rule_id}/delete")
async def rules_delete(
    rule_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    from uuid import UUID as _UUID

    try:
        rid = _UUID(rule_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Rule not found")
    rule = await db.get(Rule, rid)
    if rule is None or rule.user_id != user.id:
        raise HTTPException(status_code=404, detail="Rule not found")
    await db.delete(rule)
    await db.commit()
    return RedirectResponse("/rules", status_code=303)


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(
    request: Request,
    user: User = Depends(get_current_user),
) -> HTMLResponse:
    return templates.TemplateResponse(request, "settings.html", {"user": user})


@router.post("/settings/password")
async def settings_change_password(
    request: Request,
    current_password: str = Form(),
    new_password: str = Form(),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    if len(new_password) < 8 or len(new_password) > 128:
        request.session["flash"] = "Password must be 8-128 characters."
        return RedirectResponse("/settings", status_code=303)
    from app.security import verify_password

    if not verify_password(current_password, user.password_hash):
        request.session["flash"] = "Current password is incorrect."
        return RedirectResponse("/settings", status_code=303)
    user.password_hash = hash_password(new_password)
    await db.commit()
    request.session["flash"] = "Password updated."
    return RedirectResponse("/settings", status_code=303)


@router.get("/reset", response_class=HTMLResponse)
async def reset_page(
    request: Request, token: str = ""
) -> HTMLResponse:
    return templates.TemplateResponse(
        request, "reset.html", {"token": token}
    )


@router.post("/reset")
async def reset_submit(
    request: Request,
    token: str = Form(),
    new_password: str = Form(),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """Server-rendered password reset confirmation.

    Reuses the same logic as the JSON /auth/reset-password/confirm endpoint.
    """
    from app.security import verify_password
    from app.models import PasswordResetToken

    if len(token) < 16 or len(new_password) < 8:
        request.session["flash"] = "Token or password too short."
        return RedirectResponse("/reset", status_code=303)

    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at > now,
        )
    )
    for row in result.scalars().all():
        if verify_password(token, row.token_hash):
            user = await db.get(User, row.user_id)
            if user is None:
                continue
            user.password_hash = hash_password(new_password)
            row.used_at = now
            await db.commit()
            return RedirectResponse("/login", status_code=303)
    request.session["flash"] = "Invalid or expired token."
    return RedirectResponse("/reset", status_code=303)