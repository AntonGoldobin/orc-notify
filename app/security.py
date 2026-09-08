"""Security primitives: password hashing + JWT session tokens.

- Passwords: passlib CryptContext with argon2id (OWASP-recommended).
- Sessions: pyjwt HS256, signed with settings.jwt_secret, payload {sub: user_id}.
- Topic keys: HMAC-SHA256 over `<timestamp>:<body>`, header `X-Notifier-Signature`,
  matching ntfy.sh wire format. Constant-time compare.

Why argon2 over bcrypt: argon2id wins the Password Hashing Competition (2015)
and is resistant to GPU/ASIC attacks via memory-hardness. passlib lets us swap
to bcrypt or scrypt by changing one line if argon2 becomes problematic.
"""
from __future__ import annotations

import hashlib
import hmac
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from passlib.context import CryptContext

from app.config import get_settings

# Argon2id defaults — passlib picks sane defaults (time_cost=1, memory_cost=64MB).
# Tweak here if load testing shows signin latency spikes.
_pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def hash_password(plain: str) -> str:
    """Hash a plaintext password with argon2id.

    Returns a self-describing string like '$argon2id$v=19$m=65536,t=1,p=4$...'.
    """
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Constant-time verification. Returns False on any error (bad hash, mismatch)."""
    try:
        return _pwd_context.verify(plain, hashed)
    except (ValueError, TypeError):
        return False


def make_session_jwt(user_id: uuid.UUID) -> tuple[str, datetime]:
    """Sign a session JWT.

    Returns (token, expires_at). Token is opaque to the client; expires_at is
    useful for tests + setting the cookie Max-Age.
    """
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=settings.jwt_ttl_minutes)
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "type": "session",
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_alg)
    return token, expires_at


def decode_session_jwt(token: str) -> uuid.UUID | None:
    """Verify signature + expiry + type. Returns user_id UUID or None on any failure.

    pyjwt raises on: bad signature, expired, malformed, wrong algorithm.
    Catch all and return None — caller decides whether to 401.
    """
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_alg],
        )
    except jwt.PyJWTError:
        return None
    if payload.get("type") != "session":
        return None
    sub = payload.get("sub")
    if not isinstance(sub, str):
        return None
    try:
        return uuid.UUID(sub)
    except ValueError:
        return None


# ── Topic key verification (ntfy.sh HMAC semantics) ───────────────


def compute_topic_signature(secret: str, body: bytes, timestamp: str) -> str:
    """HMAC-SHA256 over `<timestamp>:<body>`, hex-encoded.

    Matches ntfy.sh algorithm verbatim: signature = hmac_sha256(secret, f"{ts}:{body}").
    Body MUST be the raw request bytes (not re-serialized JSON) so the sender
    and receiver hash the same bytes.
    """
    msg = timestamp.encode("ascii") + b":" + body
    return hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()


def verify_bearer_topic_key(
    secret: str,
    body: bytes,
    signature_header: str,
    timestamp_header: str,
) -> bool:
    """Constant-time verify. Returns False on any decoding error.

    Caller is responsible for enforcing timestamp freshness (ntfy uses ±5 min
    window) — we only check the HMAC. Header values are read as-is; caller
    decides whether to 401 on missing or stale timestamps.
    """
    if not signature_header or not timestamp_header:
        return False
    try:
        expected = compute_topic_signature(secret, body, timestamp_header)
        return hmac.compare_digest(expected, signature_header.lower())
    except (AttributeError, TypeError):
        return False
