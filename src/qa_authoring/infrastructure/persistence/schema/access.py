from __future__ import annotations

from sqlalchemy import (
    Boolean,
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
    true,
)

from qa_authoring.infrastructure.persistence.metadata import metadata

users = Table(
    "users",
    metadata,
    Column("id", Uuid, nullable=False),
    Column("email", Text, nullable=False),
    Column("display_name", Text, nullable=False),
    Column("subject", Text, nullable=True),
    Column("is_active", Boolean, nullable=False, server_default=true()),
    PrimaryKeyConstraint("id"),
)
Index("uq_users_email_lower", func.lower(users.c.email), unique=True)
Index(
    "uq_users_subject",
    users.c.subject,
    unique=True,
    postgresql_where=users.c.subject.isnot(None),
)

roles = Table(
    "roles",
    metadata,
    Column("id", Uuid, nullable=False),
    Column("name", Text, nullable=False),
    Column("key", Text, nullable=False),
    PrimaryKeyConstraint("id"),
    UniqueConstraint("key"),
)

# Permission codes are validated against the code enum, not a table.
role_permissions = Table(
    "role_permissions",
    metadata,
    Column("role_id", Uuid, ForeignKey("roles.id", ondelete="CASCADE"), nullable=False),
    Column("permission_code", Text, nullable=False),
    PrimaryKeyConstraint("role_id", "permission_code"),
)

user_roles = Table(
    "user_roles",
    metadata,
    Column("user_id", Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column(
        "role_id", Uuid, ForeignKey("roles.id", ondelete="RESTRICT"), nullable=False, index=True
    ),
    # clock_timestamp, not now(): several roles assigned in one transaction keep their order.
    Column(
        "created_at",
        DateTime(timezone=True),
        server_default=func.clock_timestamp(),
        nullable=False,
    ),
    PrimaryKeyConstraint("user_id", "role_id"),
)
