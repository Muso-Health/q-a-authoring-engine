from __future__ import annotations

from typing import TYPE_CHECKING, Literal
from uuid import UUID

from pydantic import BaseModel

if TYPE_CHECKING:
    from qa_authoring.application.validation_queues import (
        AudioQueueItem,
        ClinicalQueueItem,
        NamedRef,
        QueueContext,
        QueuePage,
        TranslationQueueItem,
    )


class NamedRefResponse(BaseModel):
    id: UUID
    name: str

    @classmethod
    def of(cls, ref: NamedRef) -> NamedRefResponse:
        return cls(id=ref.id, name=ref.name)


class _InContext(BaseModel):
    qaset_id: UUID
    project: NamedRefResponse
    protocol: NamedRefResponse
    theme: NamedRefResponse

    @staticmethod
    def _context(context: QueueContext) -> dict[str, NamedRefResponse]:
        return {
            "project": NamedRefResponse.of(context.project),
            "protocol": NamedRefResponse.of(context.protocol),
            "theme": NamedRefResponse.of(context.theme),
        }


class ClinicalQueueItemResponse(_InContext):
    base_language_code: str
    answer_text: str
    variant_texts: list[str]
    state: str

    @classmethod
    def of(cls, item: ClinicalQueueItem) -> ClinicalQueueItemResponse:
        return cls(
            qaset_id=item.qaset_id,
            **cls._context(item.context),
            base_language_code=item.base_language_code,
            answer_text=item.answer_text,
            variant_texts=list(item.variant_texts),
            state=item.state,
        )


class SourceTextResponse(BaseModel):
    item_id: UUID
    text: str


class TranslationQueueItemResponse(_InContext):
    kind: Literal["answer", "variant"]
    item_id: UUID
    language_code: str
    text: str
    sources: list[SourceTextResponse]
    fallback_base_answer_text: str | None
    state: str

    @classmethod
    def of(cls, item: TranslationQueueItem) -> TranslationQueueItemResponse:
        return cls(
            kind=item.kind,
            item_id=item.item_id,
            qaset_id=item.qaset_id,
            **cls._context(item.context),
            language_code=item.language_code,
            text=item.text,
            sources=[SourceTextResponse(item_id=s.item_id, text=s.text) for s in item.sources],
            fallback_base_answer_text=item.fallback_base_answer_text,
            state=item.state,
        )


class AudioQueueItemResponse(_InContext):
    audio_id: UUID
    item_kind: Literal["answer", "variant"]
    item_id: UUID
    language_code: str
    text: str
    state: str

    @classmethod
    def of(cls, item: AudioQueueItem) -> AudioQueueItemResponse:
        return cls(
            audio_id=item.audio_id,
            item_kind=item.item_kind,
            item_id=item.item_id,
            qaset_id=item.qaset_id,
            **cls._context(item.context),
            language_code=item.language_code,
            text=item.text,
            state=item.state,
        )


class ClinicalQueueResponse(BaseModel):
    items: list[ClinicalQueueItemResponse]
    next_cursor: UUID | None
    total: int

    @classmethod
    def of(cls, page: QueuePage[ClinicalQueueItem]) -> ClinicalQueueResponse:
        items = [ClinicalQueueItemResponse.of(i) for i in page.items]
        return cls(items=items, next_cursor=page.next_cursor, total=page.total)


class TranslationQueueResponse(BaseModel):
    items: list[TranslationQueueItemResponse]
    next_cursor: UUID | None
    total: int

    @classmethod
    def of(cls, page: QueuePage[TranslationQueueItem]) -> TranslationQueueResponse:
        items = [TranslationQueueItemResponse.of(i) for i in page.items]
        return cls(items=items, next_cursor=page.next_cursor, total=page.total)


class AudioQueueResponse(BaseModel):
    items: list[AudioQueueItemResponse]
    next_cursor: UUID | None
    total: int

    @classmethod
    def of(cls, page: QueuePage[AudioQueueItem]) -> AudioQueueResponse:
        items = [AudioQueueItemResponse.of(i) for i in page.items]
        return cls(items=items, next_cursor=page.next_cursor, total=page.total)
