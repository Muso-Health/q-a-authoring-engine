from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Literal
from uuid import UUID

if TYPE_CHECKING:
    from qa_authoring.domain.model.authorization import Authorization
    from qa_authoring.domain.model.permission import Permission

MAX_QUEUE_LIMIT = 200


class QueueState(StrEnum):
    """``pending`` also covers subjects never decided upon."""

    PENDING = "pending"
    REJECTED = "rejected"
    VALIDATED = "validated"
    ALL = "all"


class InvalidQueueFilterError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class QueueScope:
    """The (project, language) pairs the caller may validate in, None in either meaning any.
    Empty means nothing at all."""

    scopes: frozenset[tuple[UUID | None, UUID | None]] = frozenset()

    @classmethod
    def of(cls, authorization: Authorization, permission: Permission) -> QueueScope:
        return cls(
            frozenset(
                (g.project_id, g.language_id)
                for g in authorization.grants
                if g.permission is permission
            )
        )

    @property
    def unrestricted(self) -> bool:
        return (None, None) in self.scopes


@dataclass(frozen=True, slots=True)
class QueueFilter:
    """Project/theme, state and a keyset page (items ordered by id, those after ``cursor``),
    within the caller's ``scope``."""

    project_id: UUID | None = None
    theme_id: UUID | None = None
    state: QueueState = QueueState.PENDING
    limit: int = 50
    cursor: UUID | None = None
    scope: QueueScope = QueueScope()

    @classmethod
    def parse(
        cls,
        *,
        project_id: UUID | None,
        theme_id: UUID | None,
        state: str,
        limit: int,
        cursor: str | None,
        scope: QueueScope,
    ) -> QueueFilter:
        """Raises ``InvalidQueueFilterError``; a limit above the cap is lowered to it."""
        if state not in {s.value for s in QueueState}:
            raise InvalidQueueFilterError(
                f"invalid state {state!r}: expected one of {', '.join(QueueState)}"
            )
        if limit < 1:
            raise InvalidQueueFilterError("limit must be at least 1")
        try:
            after = None if cursor is None else UUID(cursor)
        except ValueError:
            raise InvalidQueueFilterError(f"invalid cursor {cursor!r}") from None
        return cls(
            project_id, theme_id, QueueState(state), min(limit, MAX_QUEUE_LIMIT), after, scope
        )


@dataclass(frozen=True, slots=True)
class NamedRef:
    id: UUID
    name: str


@dataclass(frozen=True, slots=True)
class QueueContext:
    project: NamedRef
    protocol: NamedRef
    theme: NamedRef


@dataclass(frozen=True, slots=True)
class ClinicalQueueItem:
    qaset_id: UUID
    context: QueueContext
    base_language_code: str
    answer_text: str
    variant_texts: tuple[str, ...]
    state: str


@dataclass(frozen=True, slots=True)
class SourceText:
    item_id: UUID
    text: str


@dataclass(frozen=True, slots=True)
class TranslationQueueItem:
    """``sources`` are the base-language items it is linked to; without any, the QA set's
    base-language answer (if any) is given as ``fallback_base_answer_text``."""

    kind: Literal["answer", "variant"]
    item_id: UUID
    qaset_id: UUID
    context: QueueContext
    language_code: str
    text: str
    sources: tuple[SourceText, ...]
    fallback_base_answer_text: str | None
    state: str


@dataclass(frozen=True, slots=True)
class AudioQueueItem:
    audio_id: UUID
    item_kind: Literal["answer", "variant"]
    item_id: UUID
    qaset_id: UUID
    context: QueueContext
    language_code: str
    text: str
    state: str


@dataclass(frozen=True, slots=True)
class QueuePage[T]:
    """``total`` counts every matching item, across pages."""

    items: tuple[T, ...]
    next_cursor: UUID | None
    total: int
