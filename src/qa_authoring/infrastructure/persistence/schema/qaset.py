from __future__ import annotations

from sqlalchemy import (
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
