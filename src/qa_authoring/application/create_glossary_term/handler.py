from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.glossary_response import GlossaryTermResult
from qa_authoring.application.glossary_support import require_language
from qa_authoring.domain.model.glossary import GlossaryTerm

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime

    from qa_authoring.application.create_glossary_term.command import CreateGlossaryTermCommand
    from qa_authoring.application.ports.glossary_repository import GlossaryRepository
    from qa_authoring.application.ports.language_repository import LanguageRepository


class CreateGlossaryTermHandler:
    def __init__(
        self,
        glossary: GlossaryRepository,
        languages: LanguageRepository,
        clock: Callable[[], datetime],
    ) -> None:
        self._glossary = glossary
        self._languages = languages
        self._clock = clock

    async def __call__(self, command: CreateGlossaryTermCommand) -> GlossaryTermResult:
        at = self._clock()
        term = GlossaryTerm.create(command.label, command.note, at=at)
        for form in command.forms:
            await require_language(self._languages, form.language_id)
            term.put_form(
                form.language_id,
                form.preferred,
                synonyms=form.synonyms,
                avoid=form.avoid,
                note=form.note,
                at=at,
            )
        await self._glossary.add(term)
        return GlossaryTermResult.of(term)
