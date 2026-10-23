from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID  # noqa: TC003 — a field type on a frozen result dataclass

if TYPE_CHECKING:
    from qa_authoring.domain.model.intent import Intent


@dataclass(frozen=True, slots=True)
class IntentResult:
    id: UUID
    text: str

    @classmethod
    def of(cls, intent: Intent) -> IntentResult:
        return cls(intent.id, intent.text)
