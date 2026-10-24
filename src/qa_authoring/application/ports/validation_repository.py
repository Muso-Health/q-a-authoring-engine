from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from qa_authoring.domain.model.validation import (
        Validation,
        ValidationState,
        ValidationSubject,
    )


class ValidationRepository(Protocol):
    """Loads and saves a Validation with its full event history; one per subject."""

    async def get_for(self, subject: ValidationSubject) -> Validation | None: ...

    async def add(self, validation: Validation) -> None: ...

    async def save(self, validation: Validation) -> None:
        """Append the events not yet stored and update the current state."""
        ...

    async def current_states(
        self, subjects: set[ValidationSubject]
    ) -> dict[ValidationSubject, ValidationState]:
        """Current state of each subject that has been decided upon (pending ones are absent)."""
        ...
