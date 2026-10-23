from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID


class IntentNotFoundError(Exception):
    def __init__(self, intent_id: UUID) -> None:
        super().__init__(f"intent {intent_id} not found")
        self.intent_id = intent_id


class IntentInUseError(Exception):
    """Raised when deleting an intent still attached to a question variant."""

    def __init__(self, intent_id: UUID) -> None:
        super().__init__(f"intent {intent_id} is attached to question variants")
        self.intent_id = intent_id
