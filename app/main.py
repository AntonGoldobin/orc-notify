"""FastAPI app entry point for orc-notify.

Mounts routers. Phase 4 cutover: no Jinja2 UI / static assets — JSON + SSE only.
The frontend SPA lives in `web/` and is served separately by `orc-notify-web`.
Health endpoint at /healthz — no auth, used by CapRover probes.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

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
        v1_events,
    )

    app.include_router(auth.router)
    app.include_router(api_keys.router, tags=["api-keys"])
    app.include_router(v1_events.router)
    app.include_router(sse.router)
    app.include_router(rules.router)
    app.include_router(topics.router)
    app.include_router(topic_keys.router)
    # Catch-all topic routes registered last.
    app.include_router(publish.router)
    app.include_router(subscribe.router)

    @app.get("/healthz", tags=["health"])
    async def healthz() -> dict:
        return {"ok": True, "app": settings.app_name}

    return app


app = create_app()
