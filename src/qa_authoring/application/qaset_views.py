from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.qaset_response import (
    LanguagePresenceResult,
    QASetLookups,
    QASetResult,
    QuestionVariantResult,
)
from qa_authoring.domain.model.validation import ValidationSubject

if TYPE_CHECKING:
    from uuid import UUID

    from qa_authoring.application.ports.category_repository import CategoryRepository
    from qa_authoring.application.ports.intent_repository import IntentRepository
    from qa_authoring.application.ports.validation_repository import ValidationRepository
    from qa_authoring.domain.model.qaset import QASet


class QASetViews:
    """Builds the read views of a QA set (whole, one language presence, one variant), resolving
    what lives outside the aggregate: catalogue texts and current validation states."""

    def __init__(
        self,
        intents: IntentRepository,
        categories: CategoryRepository,
        validations: ValidationRepository,
    ) -> None:
        self._intents = intents
        self._categories = categories
        self._validations = validations

    async def qaset(self, qaset: QASet) -> QASetResult:
        return QASetResult.of(qaset, await self.lookups(qaset))

    async def presence(self, qaset: QASet, language_id: UUID) -> LanguagePresenceResult:
        return LanguagePresenceResult.of(
            qaset, qaset.presence(language_id), await self.lookups(qaset)
        )

    async def variant(self, qaset: QASet, variant_id: UUID) -> QuestionVariantResult:
        return QuestionVariantResult.of(
            qaset, qaset.variant_by_id(variant_id), await self.lookups(qaset)
        )

    async def lookups(self, qaset: QASet) -> QASetLookups:
        intent_ids = {i for variant in qaset.variants for i in variant.intent_ids}
        category_ids = set(qaset.category_ids)
        intents = await self._intents.get_many(intent_ids) if intent_ids else {}
        categories = await self._categories.get_many(category_ids) if category_ids else {}
        subjects = {
            ValidationSubject.for_qaset(qaset.id),
            *(ValidationSubject.for_answer(a.id) for a in qaset.answers),
            *(ValidationSubject.for_variant(v.id) for v in qaset.variants),
            *(ValidationSubject.for_audio(a.id) for a in qaset.audios),
        }
        return QASetLookups(
            intent_texts={i: intent.text for i, intent in intents.items()},
            category_names={c: category.name for c, category in categories.items()},
            validation_states=await self._validations.current_states(subjects),
        )
