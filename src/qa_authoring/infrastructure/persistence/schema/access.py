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
    text,
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

# Nulls are wildcards (any project / any language). The scope is unique per user and role with
# nulls compared as a value: PostgreSQL 14 has no NULLS NOT DISTINCT, hence the coalesce.
_ANY = text("'00000000-0000-0000-0000-000000000000'::uuid")

user_role_assignments = Table(
    "user_role_assignments",
    metadata,
    Column("id", Uuid, nullable=False),
    Column("user_id", Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column(
        "role_id", Uuid, ForeignKey("roles.id", ondelete="RESTRICT"), nullable=False, index=True
    ),
    Column(
        "project_id",
        Uuid,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    ),
    Column(
        "language_id",
        Uuid,
        ForeignKey("languages.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    ),
    # clock_timestamp, not now(): several roles assigned in one transaction keep their order.
    Column(
        "created_at",
        DateTime(timezone=True),
        server_default=func.clock_timestamp(),
        nullable=False,
    ),
    PrimaryKeyConstraint("id"),
)
Index(
    "uq_user_role_assignments_scope",
    user_role_assignments.c.user_id,
    user_role_assignments.c.role_id,
    func.coalesce(user_role_assignments.c.project_id, _ANY),
    func.coalesce(user_role_assignments.c.language_id, _ANY),
    unique=True,
)
