from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    PrimaryKeyConstraint,
    Table,
    Text,
    Uuid,
)

from qa_authoring.infrastructure.persistence.metadata import metadata

documentation = Table(
    "documentation",
    metadata,
    Column("id", Uuid, nullable=False),
    Column(
        "theme_id", Uuid, ForeignKey("themes.id", ondelete="CASCADE"), nullable=False, index=True
    ),
    Column("filename", Text, nullable=False),
    Column("mime_type", Text, nullable=False),
    Column("size_bytes", BigInteger, nullable=False),
    Column("checksum_sha256", Text, nullable=False),
    Column("storage_uri", Text, nullable=False, index=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    PrimaryKeyConstraint("id"),
)
