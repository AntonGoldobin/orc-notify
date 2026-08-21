"""Webhook secret encryption at rest.

We can't bcrypt-then-HMAC because bcrypt is too slow per-request (~50ms).
Instead we Fernet-encrypt the raw secret using `settings.webhook_secret_key`,
storing ciphertext in `agents.webhook_secret_ct`. On HMAC verify we decrypt
once per request (~10µs) and use the plaintext for sha256.

Key rotation: to rotate, set the new key as the active one and have a small
migration script re-encrypt rows. For v1 we accept that rotation is manual.
"""
from __future__ import annotations

from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings


class SecretKeyError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    key = get_settings().webhook_secret_key
    if not key:
        raise SecretKeyError(
            "WEBHOOK_SECRET_KEY is empty. Generate one with "
            "`python -c 'from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())'` and set it in .env."
        )
    try:
        return Fernet(key.encode())
    except (ValueError, TypeError) as exc:
        raise SecretKeyError(
            f"WEBHOOK_SECRET_KEY is not a valid Fernet key: {exc}"
        ) from exc


def encrypt_secret(raw: str) -> str:
    """Fernet-encrypt a raw webhook secret. Returns urlsafe-base64 ciphertext."""
    return _fernet().encrypt(raw.encode()).decode()


def decrypt_secret(ciphertext: str) -> str:
    """Fernet-decrypt a stored webhook secret. Raises SecretKeyError on bad key/ct."""
    try:
        return _fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise SecretKeyError(
            "Failed to decrypt webhook secret — key may have been rotated. "
            "Re-encrypt stored rows with the new key."
        ) from exc