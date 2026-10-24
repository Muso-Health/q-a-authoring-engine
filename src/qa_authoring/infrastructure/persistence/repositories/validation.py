from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any

from sqlalchemy import insert, or_, select, update

from qa_authoring.domain.model.validation import (
    Validation,
    ValidationEvent,
    ValidationState,
    ValidationSubject,
)
from qa_authoring.infrastructure.persistence.schema.validation import (
    validation_events,
    validations,
)

if TYPE_CHECKING:
    from sqlalchemy import ColumnElement
    from sqlalchemy.ext.asyncio import AsyncConnection

_SUBJECT_COLUMNS = ("qaset_id", "answer_id", "variant_id", "audio_id")


def _subject_filter(subject: ValidationSubject) -> ColumnElement[bool]:
    [(column, value)] = [
        (c, getattr(subject, c)) for c in _SUBJECT_COLUMNS if getattr(subject, c) is not None
    ]
    condition: ColumnElement[bool] = validations.c[column] == value
    return condition


def _subject_of(row: Any) -> ValidationSubject:
    return ValidationSubject(**{c: getattr(row, c) for c in _SUBJECT_COLUMNS})


def _state(value: str | None) -> ValidationState | None:
    return None if value is None else ValidationState(value)


class PostgresValidationRepository:
    """A validation and its append-only event history; events are only ever inserted."""

    def __init__(self, connection: AsyncConnection) -> None:
        self._connection = connection

    async def get_for(self, subject: ValidationSubject) -> Validation | None:
        row = (
            await self._connection.execute(select(validations).where(_subject_filter(subject)))
        ).one_or_none()
        if row is None:
            return None
        events = [
            ValidationEvent(
                id=e.id,
                sequence=e.sequence,
                from_state=_state(e.from_state),
                to_state=ValidationState(e.to_state),
                note=e.note,
                actor_user_id=e.actor_user_id,
                occurred_at=e.occurred_at,
            )
            for e in await self._connection.execute(
                select(validation_events)
                .where(validation_events.c.validation_id == row.id)
                .order_by(validation_events.c.sequence)
            )
        ]
        return Validation(row.id, _subject_of(row), events)

    async def add(self, validation: Validation) -> None:
        subject = validation.subject
        await self._connection.execute(
            insert(validations).values(
                id=validation.id,
                kind=validation.kind.value,
                current_state=validation.current_state.value,
                updated_at=validation.events[-1].occurred_at,
                **{c: getattr(subject, c) for c in _SUBJECT_COLUMNS},
            )
        )
        await self._insert_events(validation, validation.events)

    async def save(self, validation: Validation) -> None:
        stored = await self._connection.scalar(
            select(validation_events.c.sequence)
            .where(validation_events.c.validation_id == validation.id)
            .order_by(validation_events.c.sequence.desc())
            .limit(1)
        )
        await self._insert_events(
            validation, [e for e in validation.events if e.sequence > (stored or 0)]
        )
        await self._connection.execute(
            update(validations)
            .where(validations.c.id == validation.id)
            .values(
                current_state=validation.current_state.value,
                updated_at=validation.events[-1].occurred_at,
            )
        )

    async def current_states(
        self, subjects: set[ValidationSubject]
    ) -> dict[ValidationSubject, ValidationState]:
        if not subjects:
            return {}
        by_column: defaultdict[str, list[Any]] = defaultdict(list)
        for subject in subjects:
            for column in _SUBJECT_COLUMNS:
                if (value := getattr(subject, column)) is not None:
                    by_column[column].append(value)
        rows = await self._connection.execute(
            select(validations).where(
                or_(*(validations.c[c].in_(values) for c, values in by_column.items()))
            )
        )
        return {_subject_of(row): ValidationState(row.current_state) for row in rows}

    async def _insert_events(
        self, validation: Validation, events: tuple[ValidationEvent, ...] | list[ValidationEvent]
    ) -> None:
        if events:
            await self._connection.execute(
                insert(validation_events),
                [
                    {
                        "id": e.id,
                        "validation_id": validation.id,
                        "sequence": e.sequence,
                        "from_state": None if e.from_state is None else e.from_state.value,
                        "to_state": e.to_state.value,
                        "note": e.note,
                        "actor_user_id": e.actor_user_id,
                        "occurred_at": e.occurred_at,
                    }
                    for e in events
                ],
            )
