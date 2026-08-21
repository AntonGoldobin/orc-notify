"""Auth router: register, login, logout, me, password reset.

All endpoints return JSON. Cookie is set via Response.set_cookie; we accept an
optional `response: Response` parameter and modify it in place.

Password reset (v1, no email): we generate a token, store its bcrypt hash with
a 1h expiry, and print `{public_base_url}/reset?token=...` to stdout. Operators
on the VPS capture the line from `docker logs srv-captain--notifier` and deliver
it manually. This is acceptable for the single-VPS deployment; SMTP is out of
scope for v1.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.deps import cookie_settings, get_current_user, get_db
from app.models import PasswordResetToken, User
from app.security import (
    hash_password,
    make_session_jwt,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


# ── Schemas ────────────────────────────────────────────────────────


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class ResetRequestIn(BaseModel):
    email: EmailStr


class ResetConfirmIn(BaseModel):
    token: str = Field(min_length=16)
    new_password: str = Field(min_length=8, max_length=128)


class UserOut(BaseModel):
    id: str
    email: str
    created_at: datetime

    @classmethod
    def from_user(cls, user: User) -> "UserOut":
        return cls(
            id=str(user.id),
            email=user.email,
            created_at=user.created_at,
        )


# ── Helpers ────────────────────────────────────────────────────────


def _set_session_cookie(response: Response, token: str) -> None:
    """Apply the configured cookie attrs + value."""
    response.set_cookie(value=token, **cookie_settings())


async def _issue_session(response: Response, user: User) -> UserOut:
    token, _expires = make_session_jwt(user.id)
    _set_session_cookie(response, token)
    return UserOut.from_user(user)


# ── Endpoints ──────────────────────────────────────────────────────


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterIn,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> UserOut:
    user = User(email=body.email, password_hash=hash_password(body.password))
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )
    await db.refresh(user)
    return await _issue_session(response, user)


@router.post("/login", response_model=UserOut)
async def login(
    body: LoginIn,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> UserOut:
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    # Always run a hash verify to keep timing roughly constant for unknown emails.
    dummy = "$argon2id$v=19$m=65536,t=1,p=4$" + "A" * 22 + "$" + "B" * 43
    if user is None or not verify_password(body.password, user.password_hash):
        if user is None:
            verify_password(body.password, dummy)  # constant-time-ish
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    return await _issue_session(response, user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response) -> Response:
    # Starlette's delete_cookie() doesn't accept max_age; set empty value + expires=0.
    settings = get_settings()
    response.set_cookie(
        key=cookie_settings()["key"],
        value="",
        max_age=0,
        expires=0,
        path=cookie_settings()["path"],
        domain=cookie_settings()["domain"],
        secure=cookie_settings()["secure"],
        httponly=cookie_settings()["httponly"],
        samesite=cookie_settings()["samesite"],
    )
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.from_user(user)


@router.post("/reset-password", status_code=status.HTTP_202_ACCEPTED)
async def reset_password_request(
    body: ResetRequestIn,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Issue a reset token. Always returns 202 to avoid email-enumeration leaks.

    The raw token + reset URL are PRINTED TO STDOUT (single-VPS deployment).
    """
    settings = get_settings()
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if user is None:
        verify_password(
            "decoy", "$argon2id$v=19$m=65536,t=1,p=4$" + "A" * 22 + "$" + "B" * 43
        )
        return {"status": "ok"}
    raw_token = secrets.token_urlsafe(32)
    token = PasswordResetToken(
        user_id=user.id,
        token_hash=hash_password(raw_token),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    db.add(token)
    await db.commit()
    reset_url = f"{settings.public_base_url.rstrip('/')}/reset?token={raw_token}"
    print(f"[reset-password] user={user.email} url={reset_url}", flush=True)
    return {"status": "ok"}


@router.post("/reset-password/confirm", status_code=status.HTTP_204_NO_CONTENT)
async def reset_password_confirm(
    body: ResetConfirmIn,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Consume a reset token: find unused, unexpired row matching the bcrypt."""
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at > now,
        )
    )
    for row in result.scalars().all():
        if verify_password(body.token, row.token_hash):
            user = await db.get(User, row.user_id)
            if user is None:
                continue
            user.password_hash = hash_password(body.new_password)
            row.used_at = now
            await db.commit()
            return Response(status_code=status.HTTP_204_NO_CONTENT)
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Invalid or expired reset token",
    )
