"""FastAPI app entry point for orc-notify.

Mounts routers. Templates + static dirs created lazily on first request.
Health endpoint at /healthz — no auth, used by CapRover probes.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.config import get_settings
from app.db import dispose_engine, get_engine
from app.services.prune import start_prune_task, stop_prune_task

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Eagerly init engine so first request doesn't pay the connection cost.
    engine = get_engine()
    # Smoke check on startup — fail fast if DB is unreachable.
    try:
        async with engine.connect() as conn:
            await conn.exec_driver_sql("SELECT 1")
    except Exception as exc:  # noqa: BLE001
        # Don't crash the app — log and let the first request surface it.
        logger.warning("orc-notify startup db check failed: %s", exc)
    # Start the TTL prune background task.
    start_prune_task(app)
    try:
        yield
    finally:
        await stop_prune_task(app)
        await dispose_engine()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url=None,
    )

    # Cookie-signed sessions for flash messages (UI). Same secret as JWT —
    # saves us a second secret to manage in env.
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.jwt_secret,
        same_site=settings.cookie_samesite,
        https_only=settings.cookie_secure,
        max_age=settings.jwt_ttl_minutes * 60,
    )

    # Static + templates — only mounted if dirs exist (allows tests to skip).
    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

    # Routers — order matters. Specific paths must register BEFORE the
    # catch-all `POST /<topic>` (publish router). Same for `GET /<topic>/...`
    # in subscribe. Existing routers all use multi-segment paths so they're
    # naturally first.
    from app.routers import (
        api_keys,
        auth,
        publish,
        rules,
        sse,
        subscribe,
        topic_keys,
        topics,
        ui,
        v1_events,
    )

    app.include_router(auth.router)
    app.include_router(api_keys.router, tags=["api-keys"])
    app.include_router(v1_events.router)
    app.include_router(sse.router)
    app.include_router(rules.router)
    app.include_router(topics.router)
    app.include_router(topic_keys.router)
    app.include_router(ui.router)
    # Catch-all topic routes registered last.
    app.include_router(publish.router)
    app.include_router(subscribe.router)

    @app.get("/healthz", tags=["health"])
    async def healthz() -> dict:
        return {"ok": True, "app": settings.app_name}

    return app


app = create_app()
