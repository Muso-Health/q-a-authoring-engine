"""catalog — projects, protocols and themes

Revision ID: 0003_catalog
Revises: 0002_languages
Create Date: 2026-10-23

"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0003_catalog"
down_revision: str | None = "0002_languages"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("base_language_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_projects"),
        sa.ForeignKeyConstraint(
            ["base_language_id"],
            ["languages.id"],
            name="fk_projects_base_language_id_languages",
            ondelete="RESTRICT",
        ),
    )
    op.create_index("ix_projects_base_language_id", "projects", ["base_language_id"])

    op.create_table(
        "protocols",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_protocols"),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_protocols_project_id_projects",
            ondelete="RESTRICT",
        ),
    )
    op.create_index("ix_protocols_project_id", "protocols", ["project_id"])

    op.create_table(
        "themes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("protocol_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_themes"),
        sa.ForeignKeyConstraint(
            ["protocol_id"],
            ["protocols.id"],
            name="fk_themes_protocol_id_protocols",
            ondelete="RESTRICT",
        ),
    )
    op.create_index("ix_themes_protocol_id", "themes", ["protocol_id"])


def downgrade() -> None:
    op.drop_table("themes")
    op.drop_table("protocols")
    op.drop_table("projects")
