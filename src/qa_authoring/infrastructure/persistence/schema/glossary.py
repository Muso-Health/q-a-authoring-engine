from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    PrimaryKeyConstraint,
    Table,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY

from qa_authoring.infrastructure.persistence.metadata import metadata

glossary_terms = Table(
    "glossary_terms",
    metadata,
    Column("id", Uuid, nullable=False),
    Column("label", Text, nullable=False),
    Column("note", Text, nullable=True),
    Column("status", Text, nullable=False),
    # The label and every form string, folded for search (see GlossaryTerm.search_text). Not
    # indexed: a contains-search scans it, and a B-tree would cap the size of a term.
    Column("search_text", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    PrimaryKeyConstraint("id"),
    CheckConstraint("status IN ('active', 'archived')", name="status"),
)
Index("ix_glossary_terms_status_label", glossary_terms.c.status, func.lower(glossary_terms.c.label))

glossary_forms = Table(
    "glossary_forms",
    metadata,
    Column("id", Uuid, nullable=False),
    Column("term_id", Uuid, ForeignKey("glossary_terms.id", ondelete="CASCADE"), nullable=False),
    Column(
        "language_id",
        Uuid,
        ForeignKey("languages.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    ),
    Column("preferred", Text, nullable=False),
    Column("synonyms", ARRAY(Text), server_default=text("'{}'"), nullable=False),
    Column("avoid", ARRAY(Text), server_default=text("'{}'"), nullable=False),
    Column("note", Text, nullable=True),
    PrimaryKeyConstraint("id"),
    # Also serves as the index on term_id.
    UniqueConstraint("term_id", "language_id"),
)
