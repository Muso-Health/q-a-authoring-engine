"""translation links — symmetric pairs of answers and of question variants

Revision ID: 0006_translation_links
Revises: 0005_creation_order
Create Date: 2026-10-23

"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0006_translation_links"
down_revision: str | None = "0005_creation_order"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_KINDS = (
    ("answer_translation_links", "answer", "answers"),
    ("variant_translation_links", "variant", "question_variants"),
)


def upgrade() -> None:
    for name, item, item_table in _KINDS:
        low, high = f"{item}_low_id", f"{item}_high_id"
        op.create_table(
            name,
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("qaset_id", sa.Uuid(), nullable=False),
            sa.Column(low, sa.Uuid(), nullable=False),
            sa.Column(high, sa.Uuid(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("id", name=f"pk_{name}"),
            sa.ForeignKeyConstraint(
                ["qaset_id"], ["qasets.id"], name=f"fk_{name}_qaset_id_qasets", ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(
                [low],
                [f"{item_table}.id"],
                name=f"fk_{name}_{low}_{item_table}",
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                [high],
                [f"{item_table}.id"],
                name=f"fk_{name}_{high}_{item_table}",
                ondelete="CASCADE",
            ),
            sa.UniqueConstraint("qaset_id", low, high, name=f"uq_{name}_pair"),
            sa.CheckConstraint(f"{low} < {high}", name=op.f(f"ck_{name}_canonical_pair")),
        )
        op.create_index(f"ix_{name}_{low}", name, [low])
        op.create_index(f"ix_{name}_{high}", name, [high])


def downgrade() -> None:
    for name, _, _ in reversed(_KINDS):
        op.drop_table(name)
