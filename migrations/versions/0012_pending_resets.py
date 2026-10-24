"""pending resets — a validation returns to pending when its content changes

Revision ID: 0012_pending_resets
Revises: 0011_validations
Create Date: 2026-10-24

"""

from __future__ import annotations

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0012_pending_resets"
down_revision: str | None = "0011_validations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_DECISIONS = "('validated', 'rejected')"
_STATES = "('validated', 'rejected', 'pending')"


def _replace(current_states: str, event_check: str) -> None:
    op.drop_constraint(op.f("ck_validations_current_state"), "validations", type_="check")
    op.create_check_constraint(
        op.f("ck_validations_current_state"), "validations", f"current_state IN {current_states}"
    )
    op.drop_constraint(op.f("ck_validation_events_states"), "validation_events", type_="check")
    op.create_check_constraint(
        op.f("ck_validation_events_states"), "validation_events", event_check
    )


def upgrade() -> None:
    # A history starts with a decision; pending is only reached by a reset.
    _replace(
        _STATES,
        f"to_state IN {_STATES} AND (from_state IS NOT NULL OR to_state IN {_DECISIONS})"
        f" AND (from_state IS NULL OR from_state IN {_STATES})",
    )


def downgrade() -> None:
    # Pending resets cannot be represented before this revision: drop them, newest first, and
    # restore each validation's state from its last remaining event.
    op.execute("DELETE FROM validation_events WHERE to_state = 'pending' OR from_state = 'pending'")
    op.execute(
        "UPDATE validations v SET current_state = e.to_state FROM validation_events e "
        "WHERE e.validation_id = v.id AND e.sequence = "
        "(SELECT max(sequence) FROM validation_events WHERE validation_id = v.id)"
    )
    _replace(
        _DECISIONS,
        f"to_state IN {_DECISIONS} AND (from_state IS NULL OR from_state IN {_DECISIONS})",
    )
