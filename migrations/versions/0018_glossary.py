"""glossary — the global Muso glossary: terms and their per-language forms

Revision ID: 0018_glossary
Revises: 0017_variant_clock_timestamp
Create Date: 2026-10-27

"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0018_glossary"
down_revision: str | None = "0017_variant_clock_timestamp"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "glossary_terms",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("search_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_glossary_terms"),
        sa.CheckConstraint(
            "status IN ('active', 'archived')", name=op.f("ck_glossary_terms_status")
        ),
    )
    op.create_index(
        "ix_glossary_terms_status_label",
        "glossary_terms",
        ["status", sa.text("lower(label)")],
    )
    op.create_table(
        "glossary_forms",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("term_id", sa.Uuid(), nullable=False),
        sa.Column("language_id", sa.Uuid(), nullable=False),
        sa.Column("preferred", sa.Text(), nullable=False),
        sa.Column(
            "synonyms", postgresql.ARRAY(sa.Text()), server_default=sa.text("'{}'"), nullable=False
        ),
        sa.Column(
            "avoid", postgresql.ARRAY(sa.Text()), server_default=sa.text("'{}'"), nullable=False
        ),
        sa.Column("note", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_glossary_forms"),
        sa.ForeignKeyConstraint(
            ["term_id"],
            ["glossary_terms.id"],
            name="fk_glossary_forms_term_id_glossary_terms",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["language_id"],
            ["languages.id"],
            name="fk_glossary_forms_language_id_languages",
            ondelete="RESTRICT",
        ),
        # Also serves as the index on term_id.
        sa.UniqueConstraint("term_id", "language_id", name="uq_glossary_forms_term_id_language_id"),
    )
    op.create_index("ix_glossary_forms_language_id", "glossary_forms", ["language_id"])


def downgrade() -> None:
    op.drop_table("glossary_forms")
    op.drop_table("glossary_terms")
