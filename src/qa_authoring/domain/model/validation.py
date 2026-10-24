from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import datetime  # noqa: TC003 — a field type on a frozen dataclass
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from qa_authoring.domain.value_objects.naming import clean_description

if TYPE_CHECKING:
    from collections.abc import Iterable


class ValidationKind(StrEnum):
    CLINICAL = "clinical"
    TRANSLATION = "translation"
    AUDIO = "audio"


class ValidationState(StrEnum):
    """A recorded decision. A subject never decided upon is pending: it has no Validation."""

    VALIDATED = "validated"
    REJECTED = "rejected"


class InvalidDecisionError(ValueError):
    def __init__(self, decision: str) -> None:
        super().__init__(f"invalid decision {decision!r}: expected 'validated' or 'rejected'")
        self.decision = decision


class InvalidValidationSubjectError(ValueError):
    """Raised when a validation subject does not name exactly one item."""


class InvalidValidationHistoryError(ValueError):
    """Raised when a validation's history is not a well-formed chain of decisions."""


def parse_decision(decision: str) -> ValidationState:
    try:
        return ValidationState(decision)
    except ValueError as exc:
        raise InvalidDecisionError(decision) from exc


@dataclass(frozen=True, slots=True)
class ValidationSubject:
    """Exactly one validated item; its kind follows from which one it is."""

    qaset_id: UUID | None = None
    answer_id: UUID | None = None
    variant_id: UUID | None = None
    audio_id: UUID | None = None

    def __post_init__(self) -> None:
        if sum(getattr(self, f.name) is not None for f in fields(self)) != 1:
            raise InvalidValidationSubjectError("a validation subject names exactly one item")

    @classmethod
    def for_qaset(cls, qaset_id: UUID) -> ValidationSubject:
        return cls(qaset_id=qaset_id)

    @classmethod
    def for_answer(cls, answer_id: UUID) -> ValidationSubject:
        return cls(answer_id=answer_id)

    @classmethod
    def for_variant(cls, variant_id: UUID) -> ValidationSubject:
        return cls(variant_id=variant_id)

    @classmethod
    def for_audio(cls, audio_id: UUID) -> ValidationSubject:
        return cls(audio_id=audio_id)

    @property
    def kind(self) -> ValidationKind:
        if self.qaset_id is not None:
            return ValidationKind.CLINICAL
        if self.audio_id is not None:
            return ValidationKind.AUDIO
        return ValidationKind.TRANSLATION


@dataclass(frozen=True, slots=True)
class ValidationEvent:
    """One decision; ``sequence`` orders the history (1 for the first)."""

    id: UUID
    sequence: int
    from_state: ValidationState | None
    to_state: ValidationState
    note: str | None
    actor_user_id: UUID
    occurred_at: datetime


class Validation:
    """Aggregate root: the decision history of one subject. Append-only; the current state is
    the latest event's ``to_state``. Re-deciding (either way) appends a new event."""

    __slots__ = ("_events", "_id", "_subject")

    def __init__(
        self, validation_id: UUID, subject: ValidationSubject, events: Iterable[ValidationEvent]
    ) -> None:
        self._id = validation_id
        self._subject = subject
        self._events: list[ValidationEvent] = []
        for event in events:
            self._append(event)
        if not self._events:
            raise InvalidValidationHistoryError("a validation has at least one decision")

    @classmethod
    def start(
        cls,
        subject: ValidationSubject,
        decision: ValidationState,
        *,
        actor_user_id: UUID,
        at: datetime,
        note: str | None = None,
    ) -> Validation:
        first = _event(1, None, decision, actor_user_id, at, note)
        return cls(uuid4(), subject, (first,))

    @property
    def id(self) -> UUID:
        return self._id

    @property
    def subject(self) -> ValidationSubject:
        return self._subject

    @property
    def kind(self) -> ValidationKind:
        return self._subject.kind

    @property
    def current_state(self) -> ValidationState:
        return self._events[-1].to_state

    @property
    def events(self) -> tuple[ValidationEvent, ...]:
        return tuple(self._events)

    def decide(
        self,
        decision: ValidationState,
        *,
        actor_user_id: UUID,
        at: datetime,
        note: str | None = None,
    ) -> ValidationEvent:
        last = self._events[-1]
        event = _event(last.sequence + 1, last.to_state, decision, actor_user_id, at, note)
        self._append(event)
        return event

    def _append(self, event: ValidationEvent) -> None:
        previous = self._events[-1] if self._events else None
        expected = (1, None) if previous is None else (previous.sequence + 1, previous.to_state)
        if (event.sequence, event.from_state) != expected:
            raise InvalidValidationHistoryError("decisions must chain from the previous state")
        if event.occurred_at.tzinfo is None:
            raise InvalidValidationHistoryError("decision times must be timezone-aware")
        self._events.append(event)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Validation) and other._id == self._id

    def __hash__(self) -> int:
        return hash(self._id)

    def __repr__(self) -> str:
        return f"Validation(id={self._id}, kind={self.kind}, state={self.current_state})"


def _event(
    sequence: int,
    from_state: ValidationState | None,
    to_state: ValidationState,
    actor_user_id: UUID,
    at: datetime,
    note: str | None,
) -> ValidationEvent:
    return ValidationEvent(
        id=uuid4(),
        sequence=sequence,
        from_state=from_state,
        to_state=to_state,
        note=clean_description(note),
        actor_user_id=actor_user_id,
        occurred_at=at,
    )
