from __future__ import annotations

from sqlalchemy import Column, PrimaryKeyConstraint, Table, Text, UniqueConstraint, Uuid

from qa_authoring.infrastructure.persistence.metadata import metadata

intents = Table(
    "intents",
    metadata,
    Column("id", Uuid, nullable=False),
    Column("text", Text, nullable=False),
    Column("key", Text, nullable=False),
    PrimaryKeyConstraint("id"),
    UniqueConstraint("key"),
)
