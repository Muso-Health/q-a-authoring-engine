from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID  # noqa: TC003 — a field type on a frozen dataclass

from qa_authoring.domain.model.qaset import (
    AnswerNotFoundError,
    QASet,
    QuestionVariantNotFoundError,
)
from qa_authoring.domain.model.validation import ValidationSubject

if TYPE_CHECKING:
    from qa_authoring.application.ports.qaset_repository import QASetRepository


@dataclass(frozen=True, slots=True)
class TranslationItem:
    """An answer or question variant, with the QA set holding it and its language."""

    qaset: QASet
    item_id: UUID
    language_id: UUID
    subject: ValidationSubject


async def translation_item(
    qasets: QASetRepository, *, answer_id: UUID | None, variant_id: UUID | None
) -> TranslationItem:
    subject = ValidationSubject(answer_id=answer_id, variant_id=variant_id)
    if answer_id is not None:
        qaset = await qasets.find_by_answer(answer_id)
        if qaset is None:
            raise AnswerNotFoundError(answer_id)
        language_id = qaset.answer_by_id(answer_id).language_id
        return TranslationItem(qaset, answer_id, language_id, subject)
    assert variant_id is not None
    qaset = await qasets.find_by_variant(variant_id)
    if qaset is None:
        raise QuestionVariantNotFoundError(variant_id)
    return TranslationItem(qaset, variant_id, qaset.variant_by_id(variant_id).language_id, subject)
