from __future__ import annotations

from sqlalchemy import Column, ForeignKey, PrimaryKeyConstraint, Table, Text, Uuid

from qa_authoring.infrastructure.persistence.metadata import metadata

projects = Table(
    "projects",
    metadata,
    Column("id", Uuid, nullable=False),
    Column("name", Text, nullable=False),
    Column("description", Text, nullable=True),
    Column(
        "base_language_id",
        Uuid,
        ForeignKey("languages.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    ),
    PrimaryKeyConstraint("id"),
)

protocols = Table(
    "protocols",
    metadata,
    Column("id", Uuid, nullable=False),
    Column(
        "project_id",
        Uuid,
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    ),
    Column("name", Text, nullable=False),
    Column("description", Text, nullable=True),
    PrimaryKeyConstraint("id"),
)

themes = Table(
    "themes",
    metadata,
    Column("id", Uuid, nullable=False),
    Column(
        "protocol_id",
        Uuid,
        ForeignKey("protocols.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    ),
    Column("name", Text, nullable=False),
    Column("description", Text, nullable=True),
    PrimaryKeyConstraint("id"),
)
