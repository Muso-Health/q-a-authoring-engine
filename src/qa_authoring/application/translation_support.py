from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.qaset_errors import UnknownLanguageError
from qa_authoring.domain.model.glossary_guidance import match_glossary
from qa_authoring.domain.model.qaset import SameLanguageError

if TYPE_CHECKING:
    from uuid import UUID

    from qa_authoring.application.ports.glossary_repository import GlossaryRepository
    from qa_authoring.application.ports.language_repository import LanguageRepository
    from qa_authoring.domain.model.glossary_guidance import GlossaryGuidance
    from qa_authoring.domain.model.language import Language


async def translation_languages(
    languages: LanguageRepository, source_id: UUID, target_id: UUID
) -> tuple[Language, Language]:
    """The source and target languages of a translation: registered and different."""
    if source_id == target_id:
        raise SameLanguageError(source_id)
    source = await languages.get(source_id)
    target = await languages.get(target_id)
    if target is None:
        raise UnknownLanguageError(target_id)
    assert source is not None  # an item's language is held by a RESTRICT foreign key
    return source, target


async def glossary_guidance(
    glossary: GlossaryRepository, text: str, source: Language, target: Language
) -> tuple[GlossaryGuidance, ...]:
    """The Muso glossary entries that ``text`` calls for when translated into ``target``."""
    terms = await glossary.active_with_forms_in(source.id, target.id)
    return match_glossary(text, source.id, target.id, terms)
