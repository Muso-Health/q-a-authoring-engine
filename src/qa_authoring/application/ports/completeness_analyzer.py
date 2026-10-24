from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Sequence

    from qa_authoring.domain.model.language import Language


class CompletenessEngineError(Exception):
    """The analysis failed or returned nothing usable. The message never quotes the model."""

    def __init__(self, reason: str = "failed") -> None:
        super().__init__(f"completeness analysis {reason}")


class CompletenessAnalyzerPort(Protocol):
    async def analyze(
        self, documentation: str, answers: Sequence[str], language: Language
    ) -> tuple[str, ...]:
        """The notions of ``documentation`` that no answer covers, written in ``language``
        (empty when everything is covered). Raises ``CompletenessEngineError``."""
        ...
