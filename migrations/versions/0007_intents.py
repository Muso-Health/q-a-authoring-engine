"""intents — the global intent catalogue and its attachment to question variants

Revision ID: 0007_intents
Revises: 0006_translation_links
Create Date: 2026-10-23

"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0007_intents"
down_revision: str | None = "0006_translation_links"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "intents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("key", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_intents"),
        sa.UniqueConstraint("key", name="uq_intents_key"),
    )
    op.create_table(
        "variant_intents",
        sa.Column("variant_id", sa.Uuid(), nullable=False),
        sa.Column("intent_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("variant_id", "intent_id", name="pk_variant_intents"),
        sa.ForeignKeyConstraint(
            ["variant_id"],
            ["question_variants.id"],
            name="fk_variant_intents_variant_id_question_variants",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["intent_id"],
            ["intents.id"],
            name="fk_variant_intents_intent_id_intents",
            ondelete="RESTRICT",
        ),
    )
    op.create_index("ix_variant_intents_variant_id", "variant_intents", ["variant_id"])
    op.create_index("ix_variant_intents_intent_id", "variant_intents", ["intent_id"])


def downgrade() -> None:
    op.drop_table("variant_intents")
    op.drop_table("intents")
