"""Pytest fixtures.

Tests use an in-memory SQLite DB so we don't need Postgres running. We create
tables via `Base.metadata.create_all` (alembic is for prod migrations). CITEXT
becomes TEXT under sqlite — that's fine for auth tests since email is
case-insensitive in the constraint check via Pydantic EmailStr normalization,
not the SQL column.

JWT_SECRET is fixed per-test-session so JWT roundtrips work. COOKIE_SECURE=False
keeps TestClient cookie handling simple (no HTTPS required).
"""
from __future__ import annotations

import os

# Set env BEFORE importing app modules so Settings() picks them up.
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("JWT_SECRET", "test-secret-do-not-use-in-prod-please-32chars")
os.environ.setdefault("COOKIE_SECURE", "false")
os.environ.setdefault("JWT_TTL_MINUTES", "60")

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import get_settings
from app.db import get_db
from app.main import app
from app.models import Base

get_settings.cache_clear()  # type: ignore[attr-defined]


@pytest_asyncio.fixture
async def db_engine():
    """Fresh in-memory sqlite per test, with all tables created."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine):
    """Single AsyncSession bound to the test engine."""
    sessionmaker = async_sessionmaker(db_engine, expire_on_commit=False)
    async with sessionmaker() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_engine):
    """Async HTTP client wired to the FastAPI app with get_db overridden."""

    sessionmaker = async_sessionmaker(db_engine, expire_on_commit=False)

    async def _override_get_db():
        async with sessionmaker() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
    app.dependency_overrides.clear()
