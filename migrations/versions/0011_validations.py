"""validations — clinical, translation and audio decisions with their full history

Revision ID: 0011_validations
Revises: 0010_access
Create Date: 2026-10-24

"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0011_validations"
down_revision: str | None = "0010_access"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_STATES = "('validated', 'rejected')"
_SUBJECT_MATCHES_KIND = (
    "(kind = 'clinical' AND qaset_id IS NOT NULL AND answer_id IS NULL"
    " AND variant_id IS NULL AND audio_id IS NULL)"
    " OR (kind = 'translation' AND qaset_id IS NULL AND audio_id IS NULL"
    " AND (answer_id IS NULL) <> (variant_id IS NULL))"
    " OR (kind = 'audio' AND audio_id IS NOT NULL AND qaset_id IS NULL"
    " AND answer_id IS NULL AND variant_id IS NULL)"
)


def upgrade() -> None:
    op.create_table(
        "validations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("qaset_id", sa.Uuid(), nullable=True),
        sa.Column("answer_id", sa.Uuid(), nullable=True),
        sa.Column("variant_id", sa.Uuid(), nullable=True),
        sa.Column("audio_id", sa.Uuid(), nullable=True),
        sa.Column("current_state", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_validations"),
        sa.ForeignKeyConstraint(
            ["qaset_id"], ["qasets.id"], name="fk_validations_qaset_id_qasets", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["answer_id"],
            ["answers.id"],
            name="fk_validations_answer_id_answers",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["variant_id"],
            ["question_variants.id"],
            name="fk_validations_variant_id_question_variants",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["audio_id"], ["audios.id"], name="fk_validations_audio_id_audios", ondelete="CASCADE"
        ),
        # One validation per subject; each also serves as that column's index.
        sa.UniqueConstraint("qaset_id", name="uq_validations_qaset_id"),
        sa.UniqueConstraint("answer_id", name="uq_validations_answer_id"),
        sa.UniqueConstraint("variant_id", name="uq_validations_variant_id"),
        sa.UniqueConstraint("audio_id", name="uq_validations_audio_id"),
        sa.CheckConstraint(_SUBJECT_MATCHES_KIND, name=op.f("ck_validations_subject_matches_kind")),
        sa.CheckConstraint(
            f"current_state IN {_STATES}", name=op.f("ck_validations_current_state")
        ),
    )
    # For filtering by state (e.g. exporting only validated content).
    op.create_index("ix_validations_current_state", "validations", ["current_state"])

    op.create_table(
        "validation_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("validation_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("from_state", sa.Text(), nullable=True),
        sa.Column("to_state", sa.Text(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("actor_user_id", sa.Uuid(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_validation_events"),
        sa.ForeignKeyConstraint(
            ["validation_id"],
            ["validations.id"],
            name="fk_validation_events_validation_id_validations",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name="fk_validation_events_actor_user_id_users",
            ondelete="RESTRICT",
        ),
        # Orders the history; also the index on validation_id.
        sa.UniqueConstraint(
            "validation_id", "sequence", name="uq_validation_events_validation_id_sequence"
        ),
        sa.CheckConstraint(
            f"to_state IN {_STATES} AND (from_state IS NULL OR from_state IN {_STATES})",
            name=op.f("ck_validation_events_states"),
        ),
    )
    op.create_index("ix_validation_events_actor_user_id", "validation_events", ["actor_user_id"])


def downgrade() -> None:
    op.drop_table("validation_events")
    op.drop_table("validations")
