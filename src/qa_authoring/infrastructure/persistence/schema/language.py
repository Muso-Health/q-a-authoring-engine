from __future__ import annotations

from sqlalchemy import Column, PrimaryKeyConstraint, Table, Text, UniqueConstraint, Uuid

from qa_authoring.infrastructure.persistence.metadata import metadata

languages = Table(
    "languages",
    metadata,
    Column("id", Uuid, nullable=False),
    Column("code", Text, nullable=False),
    Column("name", Text, nullable=False),
    PrimaryKeyConstraint("id"),
    UniqueConstraint("code"),
)
