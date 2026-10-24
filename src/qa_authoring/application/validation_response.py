from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime  # noqa: TC003 — a field type on frozen result dataclasses
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping
    from uuid import UUID

    from qa_authoring.domain.model.validation import Validation, ValidationKind

PENDING = "pending"


@dataclass(frozen=True, slots=True)
class ValidationEventResult:
    from_state: str | None
    to_state: str
    note: str | None
    actor_email: str
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """A subject's current state (``pending`` until the first decision) and full history."""

    kind: str
    state: str
    history: tuple[ValidationEventResult, ...]

    @classmethod
    def of(
        cls,
        kind: ValidationKind,
        validation: Validation | None,
        actor_emails: Mapping[UUID, str],
    ) -> ValidationResult:
        if validation is None:
            return cls(kind.value, PENDING, ())
        history = tuple(
            ValidationEventResult(
                None if e.from_state is None else e.from_state.value,
                e.to_state.value,
                e.note,
                actor_emails[e.actor_user_id],
                e.occurred_at,
            )
            for e in validation.events
        )
        return cls(kind.value, validation.current_state.value, history)
