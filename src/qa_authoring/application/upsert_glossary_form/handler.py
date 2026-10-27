from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.glossary_response import GlossaryTermResult
from qa_authoring.application.glossary_support import load_term_for_update, require_language

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime

    from qa_authoring.application.ports.glossary_repository import GlossaryRepository
    from qa_authoring.application.ports.language_repository import LanguageRepository
    from qa_authoring.application.upsert_glossary_form.command import UpsertGlossaryFormCommand


class UpsertGlossaryFormHandler:
    """Set the term's form in a language, replacing the one it had; the flag says whether the
    language had none."""

    def __init__(
        self,
        glossary: GlossaryRepository,
        languages: LanguageRepository,
        clock: Callable[[], datetime],
    ) -> None:
        self._glossary = glossary
        self._languages = languages
        self._clock = clock

    async def __call__(self, command: UpsertGlossaryFormCommand) -> tuple[GlossaryTermResult, bool]:
        term = await load_term_for_update(self._glossary, command.term_id)
        await require_language(self._languages, command.language_id)
        _, created = term.put_form(
            command.language_id,
            command.preferred,
            synonyms=command.synonyms,
            avoid=command.avoid,
            note=command.note,
            at=self._clock(),
        )
        await self._glossary.save(term)
        return GlossaryTermResult.of(term), created
