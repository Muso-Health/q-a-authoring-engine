from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    PrimaryKeyConstraint,
    Table,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)

from qa_authoring.infrastructure.persistence.metadata import metadata

qasets = Table(
    "qasets",
    metadata,
    Column("id", Uuid, nullable=False),
    Column(
        "theme_id", Uuid, ForeignKey("themes.id", ondelete="RESTRICT"), nullable=False, index=True
    ),
    PrimaryKeyConstraint("id"),
)

answers = Table(
    "answers",
    metadata,
    Column("id", Uuid, nullable=False),
    Column("qaset_id", Uuid, ForeignKey("qasets.id", ondelete="CASCADE"), nullable=False),
    Column(
        "language_id",
        Uuid,
        ForeignKey("languages.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    ),
    Column("text", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    PrimaryKeyConstraint("id"),
    UniqueConstraint("qaset_id", "language_id"),
)

question_variants = Table(
    "question_variants",
    metadata,
    Column("id", Uuid, nullable=False),
    Column("qaset_id", Uuid, ForeignKey("qasets.id", ondelete="CASCADE"), nullable=False),
    Column(
        "language_id",
        Uuid,
        ForeignKey("languages.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    ),
    Column("text", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    PrimaryKeyConstraint("id"),
    # A variant's language must have an answer in the same QA set; removing it removes them.
    ForeignKeyConstraint(
        ["qaset_id", "language_id"],
        ["answers.qaset_id", "answers.language_id"],
        name="fk_question_variants_qaset_id_answers",
        ondelete="CASCADE",
    ),
    Index("ix_question_variants_qaset_id_language_id", "qaset_id", "language_id"),
)


def _translation_links(name: str, item: str, item_table: str) -> Table:
    # Undirected pair stored canonically (low < high), so a pair exists at most once.
    return Table(
        name,
        metadata,
        Column("id", Uuid, nullable=False),
        Column("qaset_id", Uuid, ForeignKey("qasets.id", ondelete="CASCADE"), nullable=False),
        Column(
            f"{item}_low_id",
            Uuid,
            ForeignKey(f"{item_table}.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        Column(
            f"{item}_high_id",
            Uuid,
            ForeignKey(f"{item_table}.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
        PrimaryKeyConstraint("id"),
        UniqueConstraint("qaset_id", f"{item}_low_id", f"{item}_high_id", name=f"uq_{name}_pair"),
        CheckConstraint(f"{item}_low_id < {item}_high_id", name="canonical_pair"),
    )


answer_translation_links = _translation_links("answer_translation_links", "answer", "answers")
variant_translation_links = _translation_links(
    "variant_translation_links", "variant", "question_variants"
)

variant_intents = Table(
    "variant_intents",
    metadata,
    Column(
        "variant_id",
        Uuid,
        ForeignKey("question_variants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column(
        "intent_id", Uuid, ForeignKey("intents.id", ondelete="RESTRICT"), nullable=False, index=True
    ),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    PrimaryKeyConstraint("variant_id", "intent_id"),
)
