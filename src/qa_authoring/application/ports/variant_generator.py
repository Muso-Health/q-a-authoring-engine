from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from qa_authoring.domain.model.language import Language


class GenerationEngineError(Exception):
    """The generator failed or produced nothing usable. The message never quotes the model."""

    def __init__(self, reason: str = "failed") -> None:
        super().__init__(f"question variant generation {reason}")


class VariantGeneratorPort(Protocol):
    async def generate(
        self, answer: str, existing_questions: tuple[str, ...], context: str, language: Language
    ) -> tuple[str, ...]:
        """New candidate question variants in ``language`` that ``answer`` fully answers, seeded
        with the questions already associated with it: trimmed, non-empty, without duplicates.
        Raises ``GenerationEngineError``."""
        ...
