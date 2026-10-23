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
