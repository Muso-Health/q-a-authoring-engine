from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.validation_queues import QueueFilter, QueueScope
from qa_authoring.domain.model.permission import Permission

if TYPE_CHECKING:
    from qa_authoring.application.list_validation_queues.command import ValidationQueueQuery
    from qa_authoring.application.ports.validation_queues import ValidationQueuesPort
    from qa_authoring.application.validation_queues import (
        AudioQueueItem,
        ClinicalQueueItem,
        QueuePage,
        TranslationQueueItem,
    )


def _filter(query: ValidationQueueQuery, permission: Permission) -> QueueFilter:
    return QueueFilter.parse(
        project_id=query.project_id,
        theme_id=query.theme_id,
        state=query.state,
        limit=query.limit,
        cursor=query.cursor,
        scope=QueueScope.of(query.authorization, permission),
    )


class ListClinicalQueueHandler:
    def __init__(self, queues: ValidationQueuesPort) -> None:
        self._queues = queues

    async def __call__(self, query: ValidationQueueQuery) -> QueuePage[ClinicalQueueItem]:
        return await self._queues.clinical(_filter(query, Permission.VALIDATE_CLINICAL))


class ListTranslationQueueHandler:
    def __init__(self, queues: ValidationQueuesPort) -> None:
        self._queues = queues

    async def __call__(self, query: ValidationQueueQuery) -> QueuePage[TranslationQueueItem]:
        return await self._queues.translation(_filter(query, Permission.VALIDATE_TRANSLATION))


class ListAudioQueueHandler:
    def __init__(self, queues: ValidationQueuesPort) -> None:
        self._queues = queues

    async def __call__(self, query: ValidationQueueQuery) -> QueuePage[AudioQueueItem]:
        return await self._queues.audio(_filter(query, Permission.VALIDATE_AUDIO))
