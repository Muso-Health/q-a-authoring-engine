from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.qaset_loading import load_qaset
from qa_authoring.application.qaset_response import TranslationLinkResult
from qa_authoring.application.translation_response import TranslatedVariantResult
from qa_authoring.application.translation_support import (
    glossary_guidance,
    translation_languages,
)
from qa_authoring.domain.model.qaset import LanguagePresenceRequiredError

if TYPE_CHECKING:
    from qa_authoring.application.ports.glossary_repository import GlossaryRepository
    from qa_authoring.application.ports.language_repository import LanguageRepository
    from qa_authoring.application.ports.qaset_repository import QASetRepository
    from qa_authoring.application.qaset_views import QASetViews
    from qa_authoring.application.translate_variant.command import TranslateVariantCommand
    from qa_authoring.application.translation_engines import Translators
    from qa_authoring.application.validation_reset import ValidationResetter


class TranslateVariantHandler:
    """Translate a question variant into a language that already has an answer in the QA set,
    creating the linked variant. Checked before the engine is called; written only on success.
    The new variant starts unvalidated (and, in the base language, resets clinical review)."""

    def __init__(
        self,
        qasets: QASetRepository,
        languages: LanguageRepository,
        glossary: GlossaryRepository,
        translators: Translators,
        views: QASetViews,
        resetter: ValidationResetter,
    ) -> None:
        self._qasets = qasets
        self._languages = languages
        self._glossary = glossary
        self._translators = translators
        self._views = views
        self._resetter = resetter

    async def __call__(self, command: TranslateVariantCommand) -> TranslatedVariantResult:
        qaset = await load_qaset(self._qasets, command.qaset_id)
        variant = qaset.variant_by_id(command.variant_id)
        source, target = await translation_languages(
            self._languages, variant.language_id, command.target_language_id
        )
        if target.id not in {p.language_id for p in qaset.presences()}:
            raise LanguagePresenceRequiredError(target.id)
        translator = self._translators.get(command.engine)

        guidance = await glossary_guidance(self._glossary, variant.text, source, target)
        text = await translator.translate(variant.text, source, target, guidance)

        translated = qaset.add_variant(target.id, text)
        link = qaset.link_variants(variant.id, translated.id)
        await self._qasets.save(qaset)
        await self._resetter.content_changed(
            qaset, target.id, item=None, actor_user_id=command.actor_user_id
        )
        return TranslatedVariantResult(
            await self._views.variant(qaset, translated.id), TranslationLinkResult.of(link)
        )
