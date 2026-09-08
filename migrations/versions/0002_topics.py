"""topics + topic_keys + messages: ntfy-style topic pub/sub.

Revision ID: 0002_topics
Revises: 0001_initial
Create Date: 2026-09-08

Adds three tables alongside the existing event-fanout schema:
  - topics         (one row per user-owned pub/sub channel)
  - topic_keys     (HMAC bearer credentials scoped to a topic)
  - messages       (immutable log of published messages, TTL-pruned)

Idempotency: messages.external_id is unique per topic. Idempotent re-publish
returns the existing row instead of inserting a duplicate.

Reversibility: downgrade() drops only the new tables and their indexes.
No ALTER on existing tables.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0002_topics"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "topics",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "default_priority",
            sa.SmallInteger(),
            nullable=False,
            server_default=sa.text("3"),
        ),
        sa.Column(
            "retention_days",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("7"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("user_id", "name", name="uq_topics_user_name"),
    )
    op.create_index("ix_topics_user_created", "topics", ["user_id", "created_at"])

    op.create_table(
        "topic_keys",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "topic_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("topics.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        # Fernet-encrypted raw secret (mirror agents.webhook_secret_ct).
        # Raw plaintext is returned exactly once at create / rotate.
        sa.Column("secret_ct", sa.Text(), nullable=False),
        # CSV of scopes: any subset of "publish,read".
        sa.Column(
            "scopes",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'publish,read'"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "last_used_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.create_index("ix_topic_keys_topic", "topic_keys", ["topic_id"])

    op.create_table(
        "messages",
        # Server-generated string id (ULID-like). ntfy semantics: time-sortable
        # string identifier. TEXT PK so client can reference it across calls.
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column(
            "topic_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("topics.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Client-provided idempotency key (from "Id:" header). NULL when
        # publisher doesn't supply one. Unique per topic.
        sa.Column("external_id", sa.Text(), nullable=True),
        sa.Column(
            "time",
            sa.BigInteger(),
            nullable=False,
        ),
        sa.Column(
            "event",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'message'"),
        ),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "priority",
            sa.SmallInteger(),
            nullable=False,
            server_default=sa.text("3"),
        ),
        # ntfy uses comma-separated tags (e.g. "rotating_light,deploy,ci").
        sa.Column("tags", sa.Text(), nullable=True),
        sa.Column("click", sa.Text(), nullable=True),
        sa.Column("icon", sa.Text(), nullable=True),
        # JSONB list of action dicts.
        sa.Column("actions", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "content_type",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'text/plain'"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("topic_id", "external_id", name="uq_messages_topic_external"),
    )
    op.create_index("ix_messages_topic_time", "messages", ["topic_id", "time"])


def downgrade() -> None:
    op.drop_index("ix_messages_topic_time", table_name="messages")
    op.drop_table("messages")
    op.drop_index("ix_topic_keys_topic", table_name="topic_keys")
    op.drop_table("topic_keys")
    op.drop_index("ix_topics_user_created", table_name="topics")
    op.drop_table("topics")
