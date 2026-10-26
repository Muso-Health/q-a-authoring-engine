"""scoped role assignments — roles held per project and language (null means any)

Revision ID: 0015_scoped_role_assignments
Revises: 0014_documentation
Create Date: 2026-10-26

"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0015_scoped_role_assignments"
down_revision: str | None = "0014_documentation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ANY = "'00000000-0000-0000-0000-000000000000'::uuid"


def upgrade() -> None:
    op.create_table(
        "user_role_assignments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=True),
        sa.Column("language_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.clock_timestamp(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_user_role_assignments"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_user_role_assignments_user_id_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["roles.id"],
            name="fk_user_role_assignments_role_id_roles",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_user_role_assignments_project_id_projects",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["language_id"],
            ["languages.id"],
            name="fk_user_role_assignments_language_id_languages",
            ondelete="CASCADE",
        ),
    )
    # Nulls compared as a value (no NULLS NOT DISTINCT before PostgreSQL 15). Also the index on
    # user_id.
    op.create_index(
        "uq_user_role_assignments_scope",
        "user_role_assignments",
        [
            "user_id",
            "role_id",
            sa.text(f"coalesce(project_id, {_ANY})"),
            sa.text(f"coalesce(language_id, {_ANY})"),
        ],
        unique=True,
    )
    op.create_index("ix_user_role_assignments_role_id", "user_role_assignments", ["role_id"])
    op.create_index("ix_user_role_assignments_project_id", "user_role_assignments", ["project_id"])
    op.create_index(
        "ix_user_role_assignments_language_id", "user_role_assignments", ["language_id"]
    )
    # Every existing assignment was global.
    op.execute(
        "INSERT INTO user_role_assignments (id, user_id, role_id, created_at) "
        "SELECT gen_random_uuid(), user_id, role_id, created_at FROM user_roles"
    )
    op.drop_table("user_roles")


def downgrade() -> None:
    op.create_table(
        "user_roles",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.clock_timestamp(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("user_id", "role_id", name="pk_user_roles"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_user_roles_user_id_users", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["role_id"], ["roles.id"], name="fk_user_roles_role_id_roles", ondelete="RESTRICT"
        ),
    )
    op.create_index("ix_user_roles_role_id", "user_roles", ["role_id"])
    # Only global assignments go back: widening a scoped one to global would grant more than
    # was given, so those are dropped (fail closed).
    op.execute(
        "INSERT INTO user_roles (user_id, role_id, created_at) "
        "SELECT user_id, role_id, created_at FROM user_role_assignments "
        "WHERE project_id IS NULL AND language_id IS NULL"
    )
    op.drop_table("user_role_assignments")
