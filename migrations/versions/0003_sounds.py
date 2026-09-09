"""per-user notification sounds, attached to topics (Phase 2).

Revision ID: 0003_sounds
Revises: 0002_topics
Create Date: 2026-09-09

Adds:
  - sounds         (user-owned library of sound records: name + url)
  - topics.sound_id nullable FK to sounds.id (ON DELETE SET NULL — detaching
                    a sound must NOT cascade-delete the topic)

Why ON DELETE SET NULL on topics.sound_id: deleting a sound should leave the
topic alive with no sound, not nuke the topic. The user can re-attach another
sound afterwards.

Reversibility: downgrade() drops the FK + column, then drops the table.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0003_sounds"
down_revision: str | None = "0002_topics"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sounds",
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
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_sounds_user", "sounds", ["user_id"])

    op.add_column(
        "topics",
        sa.Column(
            "sound_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_topics_sound",
        "topics",
        "sounds",
        ["sound_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_topics_sound", "topics", type_="foreignkey")
    op.drop_column("topics", "sound_id")
    op.drop_index("ix_sounds_user", table_name="sounds")
    op.drop_table("sounds")
