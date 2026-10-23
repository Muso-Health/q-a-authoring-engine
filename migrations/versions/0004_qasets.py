"""qasets — QA sets with per-language answers and question variants

Revision ID: 0004_qasets
Revises: 0003_catalog
Create Date: 2026-10-23

"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0004_qasets"
down_revision: str | None = "0003_catalog"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "qasets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("theme_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_qasets"),
        sa.ForeignKeyConstraint(
            ["theme_id"], ["themes.id"], name="fk_qasets_theme_id_themes", ondelete="RESTRICT"
        ),
    )
    op.create_index("ix_qasets_theme_id", "qasets", ["theme_id"])

    op.create_table(
        "answers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("qaset_id", sa.Uuid(), nullable=False),
        sa.Column("language_id", sa.Uuid(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_answers"),
        sa.ForeignKeyConstraint(
            ["qaset_id"], ["qasets.id"], name="fk_answers_qaset_id_qasets", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["language_id"],
            ["languages.id"],
            name="fk_answers_language_id_languages",
            ondelete="RESTRICT",
        ),
        # Also serves as the index on qaset_id.
        sa.UniqueConstraint("qaset_id", "language_id", name="uq_answers_qaset_id_language_id"),
    )
    op.create_index("ix_answers_language_id", "answers", ["language_id"])

    op.create_table(
        "question_variants",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("qaset_id", sa.Uuid(), nullable=False),
        sa.Column("language_id", sa.Uuid(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_question_variants"),
        sa.ForeignKeyConstraint(
            ["qaset_id"],
            ["qasets.id"],
            name="fk_question_variants_qaset_id_qasets",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["language_id"],
            ["languages.id"],
            name="fk_question_variants_language_id_languages",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["qaset_id", "language_id"],
            ["answers.qaset_id", "answers.language_id"],
            name="fk_question_variants_qaset_id_answers",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_question_variants_qaset_id_language_id",
        "question_variants",
        ["qaset_id", "language_id"],
    )
    op.create_index("ix_question_variants_language_id", "question_variants", ["language_id"])


def downgrade() -> None:
    op.drop_table("question_variants")
    op.drop_table("answers")
    op.drop_table("qasets")
