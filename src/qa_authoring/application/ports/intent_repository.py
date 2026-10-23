from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from uuid import UUID

    from qa_authoring.domain.model.intent import Intent


class IntentRepository(Protocol):
    async def get_or_create(self, intent: Intent) -> tuple[Intent, bool]:
        """The stored intent with the same normalized text, or ``intent`` once inserted; the flag
        says whether it was created. Safe against a concurrent registration of the same text."""
        ...

    async def get(self, intent_id: UUID) -> Intent | None: ...

    async def get_many(self, intent_ids: set[UUID]) -> dict[UUID, Intent]:
        """The known intents among ``intent_ids``, keyed by id."""
        ...

    async def list(self, prefix: str | None = None) -> tuple[Intent, ...]:
        """Ordered by normalized text; ``prefix`` matches the start of the normalized text."""
        ...

    async def delete(self, intent_id: UUID) -> None:
        """Raises ``IntentInUseError`` if a question variant still references it."""
        ...
