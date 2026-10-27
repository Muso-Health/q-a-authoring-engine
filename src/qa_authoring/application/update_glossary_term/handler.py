from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.glossary_response import GlossaryTermResult
from qa_authoring.application.glossary_support import load_term_for_update
from qa_authoring.application.patch import UNCHANGED

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime

    from qa_authoring.application.ports.glossary_repository import GlossaryRepository
    from qa_authoring.application.update_glossary_term.command import UpdateGlossaryTermCommand


class UpdateGlossaryTermHandler:
    def __init__(self, glossary: GlossaryRepository, clock: Callable[[], datetime]) -> None:
        self._glossary = glossary
        self._clock = clock

    async def __call__(self, command: UpdateGlossaryTermCommand) -> GlossaryTermResult:
        term = await load_term_for_update(self._glossary, command.term_id)
        at = self._clock()
        if command.label is not None:
            term.relabel(command.label, at=at)
        if command.note is not UNCHANGED:
            term.annotate(command.note, at=at)
        await self._glossary.save(term)
        return GlossaryTermResult.of(term)
