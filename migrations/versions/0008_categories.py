"""categories — the global category catalogue and its attachment to QA sets

Revision ID: 0008_categories
Revises: 0007_intents
Create Date: 2026-10-24

"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0008_categories"
down_revision: str | None = "0007_intents"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "categories",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("key", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_categories"),
        sa.UniqueConstraint("key", name="uq_categories_key"),
    )
    op.create_table(
        "qaset_categories",
        sa.Column("qaset_id", sa.Uuid(), nullable=False),
        sa.Column("category_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        # Also serves as the index on qaset_id.
        sa.PrimaryKeyConstraint("qaset_id", "category_id", name="pk_qaset_categories"),
        sa.ForeignKeyConstraint(
            ["qaset_id"],
            ["qasets.id"],
            name="fk_qaset_categories_qaset_id_qasets",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.id"],
            name="fk_qaset_categories_category_id_categories",
            ondelete="RESTRICT",
        ),
    )
    op.create_index("ix_qaset_categories_category_id", "qaset_categories", ["category_id"])


def downgrade() -> None:
    op.drop_table("qaset_categories")
    op.drop_table("categories")
