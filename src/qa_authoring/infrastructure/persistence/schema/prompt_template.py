from __future__ import annotations

from sqlalchemy import Column, DateTime, ForeignKey, PrimaryKeyConstraint, Table, Text, Uuid

from qa_authoring.infrastructure.persistence.metadata import metadata

# One row per fixed key (the key is the primary key, hence unique). ``updated_by`` is null for
# a seeded default.
prompt_templates = Table(
    "prompt_templates",
    metadata,
    Column("key", Text, nullable=False),
    Column("content", Text, nullable=False),
    Column(
        "updated_by", Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=True, index=True
    ),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    PrimaryKeyConstraint("key"),
)
