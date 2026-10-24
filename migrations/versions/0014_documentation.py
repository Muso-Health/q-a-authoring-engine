"""documentation — reference files attached to themes

Revision ID: 0014_documentation
Revises: 0013_prompt_templates
Create Date: 2026-10-24

"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0014_documentation"
down_revision: str | None = "0013_prompt_templates"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "documentation",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("theme_id", sa.Uuid(), nullable=False),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("mime_type", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("checksum_sha256", sa.Text(), nullable=False),
        sa.Column("storage_uri", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_documentation"),
        sa.ForeignKeyConstraint(
            ["theme_id"],
            ["themes.id"],
            name="fk_documentation_theme_id_themes",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_documentation_theme_id", "documentation", ["theme_id"])
    # For the "is this blob still referenced?" check before deleting a shared blob.
    op.create_index("ix_documentation_storage_uri", "documentation", ["storage_uri"])


def downgrade() -> None:
    op.drop_table("documentation")
