"""audios — recording references bound to exactly one answer or one question variant

Revision ID: 0009_audios
Revises: 0008_categories
Create Date: 2026-10-24

"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0009_audios"
down_revision: str | None = "0008_categories"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audios",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("answer_id", sa.Uuid(), nullable=True),
        sa.Column("variant_id", sa.Uuid(), nullable=True),
        sa.Column("storage_uri", sa.Text(), nullable=False),
        sa.Column("mime_type", sa.Text(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("checksum_sha256", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_audios"),
        sa.ForeignKeyConstraint(
            ["answer_id"], ["answers.id"], name="fk_audios_answer_id_answers", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["variant_id"],
            ["question_variants.id"],
            name="fk_audios_variant_id_question_variants",
            ondelete="CASCADE",
        ),
        # One audio per item; each also serves as that column's index.
        sa.UniqueConstraint("answer_id", name="uq_audios_answer_id"),
        sa.UniqueConstraint("variant_id", name="uq_audios_variant_id"),
        sa.CheckConstraint(
            "(answer_id IS NULL) <> (variant_id IS NULL)",
            name=op.f("ck_audios_exactly_one_target"),
        ),
    )
    # For the "is this blob still referenced?" check before deleting a shared blob.
    op.create_index("ix_audios_storage_uri", "audios", ["storage_uri"])


def downgrade() -> None:
    op.drop_table("audios")
