from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.generate_variants.command import GeneratedVariantsResult
from qa_authoring.application.qaset_loading import load_qaset

if TYPE_CHECKING:
    from qa_authoring.application.generate_variants.command import GenerateVariantsQuery
    from qa_authoring.application.ports.language_repository import LanguageRepository
    from qa_authoring.application.ports.qaset_repository import QASetRepository
    from qa_authoring.application.ports.variant_generator import VariantGeneratorPort


class GenerateVariantsHandler:
    """Propose question variants for an answer, in the answer's language. Proposes only: nothing
    is saved; the author keeps candidates through the add-variant endpoint."""

    def __init__(
        self,
        qasets: QASetRepository,
        languages: LanguageRepository,
        generator: VariantGeneratorPort,
    ) -> None:
        self._qasets = qasets
        self._languages = languages
        self._generator = generator

    async def __call__(self, query: GenerateVariantsQuery) -> GeneratedVariantsResult:
        qaset = await load_qaset(self._qasets, query.qaset_id)
        answer = qaset.answer_by_id(query.answer_id)
        language = await self._languages.get(answer.language_id)
        assert language is not None  # an answer's language is held by a RESTRICT foreign key
        candidates = await self._generator.generate(answer.text, query.context, language)
        return GeneratedVariantsResult(candidates)
