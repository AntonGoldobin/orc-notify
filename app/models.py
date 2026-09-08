"""SQLAlchemy 2.0 declarative models for orc-notify.

8 tables:
- users (auth + account)
- password_reset_tokens (one-time reset flow)
- agents (per-user API keys; agent_id is the public identifier)
- events (one row per agent POST)
- rules (event_pattern -> channel)
- in_app_notifications (join table: events that hit a user's rules)
- topics (ntfy-style pub/sub channels — Phase 1)
- topic_keys (HMAC bearer credentials scoped to a topic — Phase 1)
- messages (immutable log of published topic messages, TTL-pruned — Phase 1)

Timestamps are TIMESTAMPTZ (Postgres-native). UUIDs as primary keys
(via uuid_generate_v4 fallback to python-side uuid4).
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    TypeDecorator,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import CITEXT, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

if TYPE_CHECKING:
    pass


class Base(DeclarativeBase):
    pass


class CIText(TypeDecorator):
    """CITEXT in Postgres, VARCHAR in SQLite (test fallback).

    Email case-insensitivity matters in prod (Postgres citext extension). In
    SQLite tests we rely on Pydantic EmailStr normalization for case handling.
    """

    impl = String
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(CITEXT())
        return dialect.type_descriptor(String(255))


class BigIntAutoInc(TypeDecorator):
    """BIGINT in Postgres, INTEGER in SQLite (test fallback).

    SQLite's `INTEGER PRIMARY KEY` is a rowid alias and supports autoincrement;
    `BIGINT PRIMARY KEY` does NOT — it's a regular column without auto-id.
    This decorator keeps BIGINT semantics in prod while letting tests use
    SQLite via metadata.create_all without manual sequence setup.
    """

    impl = BigInteger
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "sqlite":
            from sqlalchemy import Integer
            return dialect.type_descriptor(Integer())
        return dialect.type_descriptor(BigInteger())


class JSONColumn(TypeDecorator):
    """JSONB in Postgres, JSON TEXT in SQLite (test fallback).

    Same Python-side interface: native Python objects in, native Python objects
    out. SQLite stores as JSON TEXT (orjson round-trip) — sufficient for tests.
    """

    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(JSONB(astext_type=Text()))
        # SQLite: store as TEXT. SQLAlchemy's built-in JSON type would also
        # work, but using JSONColumn everywhere keeps the column type uniform.
        from sqlalchemy import JSON as _JSON
        return dialect.type_descriptor(_JSON())

    def process_bind_param(self, value, dialect):
        if dialect.name == "sqlite" and value is not None:
            import orjson
            return orjson.dumps(value).decode()
        return value

    def process_result_value(self, value, dialect):
        if dialect.name == "sqlite" and isinstance(value, str):
            import orjson
            return orjson.loads(value)
        return value


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


# ── Users ──────────────────────────────────────────────────────────


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    email: Mapped[str] = mapped_column(CIText(), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    agents: Mapped[list["Agent"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    rules: Mapped[list["Rule"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ── Agents (API keys) ─────────────────────────────────────────────


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    # Public identifier shared in HTTP headers (X-Notifier-Agent).
    agent_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    # Fernet-encrypted webhook secret. Raw secret is shown exactly once on
    # creation/rotation. We can't bcrypt-then-HMAC because bcrypt is too slow
    # per-request (~50ms). Encryption at rest via app.config.webhook_secret_key.
    webhook_secret_ct: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_event_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user: Mapped["User"] = relationship(back_populates="agents")


# ── Events ─────────────────────────────────────────────────────────


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(BigIntAutoInc, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    # ON DELETE SET NULL: agent deletion preserves events.
    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="SET NULL"),
        nullable=True,
    )
    event: Mapped[str] = mapped_column(Text, nullable=False)
    thread_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    project_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_input: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    tasks_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    errors_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pr_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("ix_events_user_received", "user_id", "received_at"),
    )


# ── Rules ──────────────────────────────────────────────────────────


class Rule(Base):
    __tablename__ = "rules"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    # Glob pattern (e.g. "thread.*", "*.failed", "*"). Compiled via fnmatch.
    event_pattern: Mapped[str] = mapped_column(Text, nullable=False)
    # For v1: only "sse". Schema flexible for future channels.
    channel: Mapped[str] = mapped_column(Text, nullable=False, default="sse")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="rules")


# ── In-app notifications (join: events × rules) ────────────────────


class InAppNotification(Base):
    __tablename__ = "in_app_notifications"

    id: Mapped[int] = mapped_column(BigIntAutoInc, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_id: Mapped[int] = mapped_column(
        BigIntAutoInc,
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
    )
    rule_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rules.id", ondelete="SET NULL"),
        nullable=True,
    )
    delivered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("ix_inapp_user_delivered", "user_id", "delivered_at"),
    )


# ── Topics (Phase 1: ntfy-style pub/sub) ──────────────────────────


class Topic(Base):
    """A user-owned pub/sub channel.

    URL `<topic>` resolves as (current_user, name). Uniqueness enforced by
    `UNIQUE(user_id, name)` — no cross-user topic visibility.
    """

    __tablename__ = "topics"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # ntfy uses 1-5; 3 is default "normal" priority.
    default_priority: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=3
    )
    # TTL prune window. Defaults to 7 days; per-topic override.
    retention_days: Mapped[int] = mapped_column(Integer, nullable=False, default=7)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    keys: Mapped[list["TopicKey"]] = relationship(
        back_populates="topic", cascade="all, delete-orphan"
    )
    messages: Mapped[list["Message"]] = relationship(
        back_populates="topic", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_topics_user_created", "user_id", "created_at"),
        UniqueConstraint("user_id", "name", name="uq_topics_user_name"),
    )


class TopicKey(Base):
    """HMAC bearer credential scoped to a single topic.

    The raw plaintext secret is Fernet-encrypted at rest (mirror of agents).
    Returned exactly once on create / rotate. Verification happens via
    `verify_bearer_topic_key` in security.py.
    """

    __tablename__ = "topic_keys"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    topic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("topics.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    # Fernet-encrypted raw HMAC key.
    secret_ct: Mapped[str] = mapped_column(Text, nullable=False)
    # CSV: any subset of "publish,read".
    scopes: Mapped[str] = mapped_column(
        Text, nullable=False, default="publish,read"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    topic: Mapped["Topic"] = relationship(back_populates="keys")


class Message(Base):
    """Immutable log entry for one published topic message.

    `id` is server-generated string (uuid4 hex — 32 chars). ntfy uses ULIDs;
    we use uuid4 for ponytail simplicity (stdlib, no extra dep, still
    effectively unique). Sortable in practice via `time` BIGINT (epoch secs).
    """

    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    topic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("topics.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Client-provided idempotency key from `Id:` header. NULL when unset.
    # Idempotent re-publish with same (topic_id, external_id) returns 200 with
    # the existing row.
    external_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    # epoch seconds — matches ntfy.sh wire format. INTEGER would overflow in 2038.
    time: Mapped[int] = mapped_column(BigInteger, nullable=False)
    event: Mapped[str] = mapped_column(Text, nullable=False, default="message")
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=3)
    # CSV: "rotating_light,deploy,ci". Wire format matches ntfy.
    tags: Mapped[str | None] = mapped_column(Text, nullable=True)
    click: Mapped[str | None] = mapped_column(Text, nullable=True)
    icon: Mapped[str | None] = mapped_column(Text, nullable=True)
    # List of action dicts; JSONB in prod, JSON TEXT in SQLite tests.
    actions: Mapped[Any | None] = mapped_column(JSONColumn, nullable=True)
    content_type: Mapped[str] = mapped_column(
        Text, nullable=False, default="text/plain"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    topic: Mapped["Topic"] = relationship(back_populates="messages")

    __table_args__ = (
        Index("ix_messages_topic_time", "topic_id", "time"),
        UniqueConstraint("topic_id", "external_id", name="uq_messages_topic_external"),
    )
