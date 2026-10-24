from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from qa_authoring.application.validation_queues import (
        AudioQueueItem,
        ClinicalQueueItem,
        QueueFilter,
        QueuePage,
        TranslationQueueItem,
    )


class ValidationQueuesPort(Protocol):
    """Read-side worklists of validation subjects, with the context a reviewer needs inline."""

    async def clinical(self, queue_filter: QueueFilter) -> QueuePage[ClinicalQueueItem]:
        """QA sets with an answer in their project's base language."""
        ...

    async def translation(self, queue_filter: QueueFilter) -> QueuePage[TranslationQueueItem]:
        """Answers and question variants outside their project's base language."""
        ...

    async def audio(self, queue_filter: QueueFilter) -> QueuePage[AudioQueueItem]: ...
