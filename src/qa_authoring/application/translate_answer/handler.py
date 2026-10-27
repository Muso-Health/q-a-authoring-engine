from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.qaset_loading import load_qaset
from qa_authoring.application.qaset_response import TranslationLinkResult
from qa_authoring.application.translation_response import TranslatedAnswerResult
from qa_authoring.application.translation_support import (
    glossary_guidance,
    translation_languages,
)
from qa_authoring.domain.model.qaset import LanguageAlreadyPresentError

if TYPE_CHECKING:
    from qa_authoring.application.ports.glossary_repository import GlossaryRepository
    from qa_authoring.application.ports.language_repository import LanguageRepository
    from qa_authoring.application.ports.qaset_repository import QASetRepository
    from qa_authoring.application.qaset_views import QASetViews
    from qa_authoring.application.translate_answer.command import TranslateAnswerCommand
    from qa_authoring.application.translation_engines import Translators
    from qa_authoring.application.validation_reset import ValidationResetter


class TranslateAnswerHandler:
    """Translate an answer into a language the QA set lacks, creating that language's answer
    linked to its source. Everything is checked before the engine is called, and nothing is
    written unless it succeeds. The new answer starts unvalidated."""

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

    async def __call__(self, command: TranslateAnswerCommand) -> TranslatedAnswerResult:
        qaset = await load_qaset(self._qasets, command.qaset_id)
        answer = qaset.answer_by_id(command.answer_id)
        source, target = await translation_languages(
            self._languages, answer.language_id, command.target_language_id
        )
        if target.id in {p.language_id for p in qaset.presences()}:
            raise LanguageAlreadyPresentError(target.id)
        translator = self._translators.get(command.engine)

        guidance = await glossary_guidance(self._glossary, answer.text, source, target)
        text = await translator.translate(answer.text, source, target, guidance)

        translated = qaset.add_language(target.id, text)
        link = qaset.link_answers(answer.id, translated.id)
        await self._qasets.save(qaset)
        await self._resetter.content_changed(
            qaset, target.id, item=None, actor_user_id=command.actor_user_id
        )
        return TranslatedAnswerResult(
            await self._views.presence(qaset, target.id), TranslationLinkResult.of(link)
        )
