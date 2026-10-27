from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.glossary_support import load_term_for_update

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime

    from qa_authoring.application.ports.glossary_repository import GlossaryRepository
    from qa_authoring.application.remove_glossary_form.command import RemoveGlossaryFormCommand


class RemoveGlossaryFormHandler:
    def __init__(self, glossary: GlossaryRepository, clock: Callable[[], datetime]) -> None:
        self._glossary = glossary
        self._clock = clock

    async def __call__(self, command: RemoveGlossaryFormCommand) -> None:
        term = await load_term_for_update(self._glossary, command.term_id)
        term.remove_form(command.language_id, at=self._clock())
        await self._glossary.save(term)
