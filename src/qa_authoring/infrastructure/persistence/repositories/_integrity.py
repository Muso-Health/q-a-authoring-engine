from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.exc import IntegrityError

UNIQUE_VIOLATION = "23505"
FOREIGN_KEY_VIOLATION = "23503"


def sqlstate(exc: IntegrityError) -> str | None:
    """The PostgreSQL SQLSTATE behind a SQLAlchemy integrity error, if the driver exposes it."""
    state: str | None = getattr(exc.orig, "sqlstate", None)
    return state


def constraint_name(exc: IntegrityError) -> str | None:
    """The name of the violated constraint, as reported by asyncpg."""
    name: str | None = getattr(getattr(exc.orig, "__cause__", None), "constraint_name", None)
    return name
