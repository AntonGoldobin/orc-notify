"""FastAPI dependencies: DB session + current user.

get_db() is the per-request async session (commit on success, rollback on error).
get_current_user() reads the `notifier_session` cookie, verifies the JWT, and
loads the User row. 401 on any failure.
"""
from __future__ import annotations

import uuid

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_db
from app.models import User
from app.security import decode_session_jwt

COOKIE_NAME = "notifier_session"


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    notifier_session: str | None = Cookie(default=None),
) -> User:
    """Auth dependency. Raises 401 if no valid session cookie."""
    if not notifier_session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Cookie"},
        )
    user_id = decode_session_jwt(notifier_session)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
            headers={"WWW-Authenticate": "Cookie"},
        )
    user = await db.get(User, user_id)
    if user is None:
        # Token signed for a user that was deleted — treat as unauthenticated.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User no longer exists",
            headers={"WWW-Authenticate": "Cookie"},
        )
    return user


def cookie_settings() -> dict:
    """Return kwargs for setting the session cookie on a Response."""
    settings = get_settings()
    return {
        "key": COOKIE_NAME,
        "httponly": True,
        "secure": settings.cookie_secure,
        "samesite": settings.cookie_samesite,
        "path": "/",
        "max_age": settings.jwt_ttl_minutes * 60,
        "domain": settings.cookie_domain,
    }


__all__ = ["COOKIE_NAME", "get_current_user", "get_db", "cookie_settings"]
