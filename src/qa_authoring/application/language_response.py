from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID  # noqa: TC003 — a field type on a frozen result dataclass

if TYPE_CHECKING:
    from qa_authoring.domain.model.language import Language


@dataclass(frozen=True, slots=True)
class LanguageResult:
    """One language as primitives — what every language use case returns to the edge."""

    id: UUID
    code: str
    name: str

    @classmethod
    def of(cls, language: Language) -> LanguageResult:
        return cls(id=language.id, code=language.code.value, name=language.name)
