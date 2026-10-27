"""question variants ordered by clock_timestamp — variants added in one transaction keep order

Revision ID: 0017_variant_clock_timestamp
Revises: 0016_variant_prompt_questions
Create Date: 2026-10-26

"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0017_variant_clock_timestamp"
down_revision: str | None = "0016_variant_prompt_questions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("question_variants", "created_at", server_default=sa.func.clock_timestamp())


def downgrade() -> None:
    op.alter_column("question_variants", "created_at", server_default=sa.func.now())
