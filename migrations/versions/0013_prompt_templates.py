"""prompt templates — the organization-wide prompt for each model use

Revision ID: 0013_prompt_templates
Revises: 0012_pending_resets
Create Date: 2026-10-24

"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0013_prompt_templates"
down_revision: str | None = "0012_pending_resets"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "prompt_templates",
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        # Null for a seeded default.
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        # One active template per key.
        sa.PrimaryKeyConstraint("key", name="pk_prompt_templates"),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["users.id"],
            name="fk_prompt_templates_updated_by_users",
            ondelete="RESTRICT",
        ),
    )
    op.create_index("ix_prompt_templates_updated_by", "prompt_templates", ["updated_by"])


def downgrade() -> None:
    op.drop_table("prompt_templates")
