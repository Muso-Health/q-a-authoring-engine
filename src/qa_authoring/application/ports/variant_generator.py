from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from qa_authoring.domain.model.language import Language


class GenerationEngineError(Exception):
    """The generator failed or produced nothing usable. The message never quotes the model."""

    def __init__(self, reason: str = "failed") -> None:
        super().__init__(f"question variant generation {reason}")


class VariantGeneratorPort(Protocol):
    async def generate(self, answer: str, context: str, language: Language) -> tuple[str, ...]:
        """Candidate question variants in ``language`` that ``answer`` fully answers: trimmed,
        non-empty, without duplicates. Raises ``GenerationEngineError``."""
        ...
