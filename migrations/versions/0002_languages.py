"""languages — the dynamic language store

Revision ID: 0002_languages
Revises: 0001_baseline
Create Date: 2026-10-23

"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0002_languages"
down_revision: str | None = "0001_baseline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "languages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_languages"),
        sa.UniqueConstraint("code", name="uq_languages_code"),
    )


def downgrade() -> None:
    op.drop_table("languages")
