from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.glossary_errors import GlossaryTermNotFoundError
from qa_authoring.application.language_errors import LanguageNotFoundError

if TYPE_CHECKING:
    from uuid import UUID

    from qa_authoring.application.ports.glossary_repository import GlossaryRepository
    from qa_authoring.application.ports.language_repository import LanguageRepository
    from qa_authoring.domain.model.glossary import GlossaryTerm


async def load_term_for_update(glossary: GlossaryRepository, term_id: UUID) -> GlossaryTerm:
    term = await glossary.get_for_update(term_id)
    if term is None:
        raise GlossaryTermNotFoundError(term_id)
    return term


async def require_language(languages: LanguageRepository, language_id: UUID) -> None:
    if await languages.get(language_id) is None:
        raise LanguageNotFoundError(language_id)
