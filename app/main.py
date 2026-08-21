"""FastAPI app entry point for orc-notify.

Mounts routers. Templates + static dirs created lazily on first request.
Health endpoint at /healthz — no auth, used by CapRover probes.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.db import dispose_engine, get_engine


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
        import logging
        logging.getLogger(__name__).warning(
            "orc-notify startup db check failed: %s", exc
        )
    yield
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

    # Static + templates — only mounted if dirs exist (allows tests to skip).
    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

    # Routers
    from app.routers import auth, api_keys, v1_events, sse, rules, ui

    app.include_router(auth.router)
    app.include_router(api_keys.router, tags=["api-keys"])
    app.include_router(v1_events.router, prefix="/v1", tags=["v1"])
    app.include_router(sse.router, tags=["events"])
    app.include_router(rules.router, prefix="/api/rules", tags=["rules"])
    app.include_router(ui.router, tags=["ui"])

    @app.get("/healthz", tags=["health"])
    async def healthz() -> dict:
        return {"ok": True, "app": settings.app_name}

    return app


app = create_app()
