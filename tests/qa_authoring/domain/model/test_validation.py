from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from qa_authoring.domain.model.validation import (
    InvalidDecisionError,
    InvalidValidationHistoryError,
    InvalidValidationSubjectError,
    Validation,
    ValidationKind,
    ValidationState,
    ValidationSubject,
    parse_decision,
)

T0 = datetime(2026, 10, 24, 9, 0, tzinfo=UTC)
ALICE, BOB = uuid4(), uuid4()


def test_parse_decision() -> None:
    assert parse_decision("validated") is ValidationState.VALIDATED
    assert parse_decision("rejected") is ValidationState.REJECTED
    for bad in ("pending", "VALIDATED", "", "ok"):
        with pytest.raises(InvalidDecisionError):
            parse_decision(bad)


def test_subject_names_exactly_one_target_and_sets_the_kind() -> None:
    assert ValidationSubject.for_qaset(uuid4()).kind is ValidationKind.CLINICAL
    assert ValidationSubject.for_answer(uuid4()).kind is ValidationKind.TRANSLATION
    assert ValidationSubject.for_variant(uuid4()).kind is ValidationKind.TRANSLATION
    assert ValidationSubject.for_audio(uuid4()).kind is ValidationKind.AUDIO
    with pytest.raises(InvalidValidationSubjectError):
        ValidationSubject()
    with pytest.raises(InvalidValidationSubjectError):
        ValidationSubject(qaset_id=uuid4(), audio_id=uuid4())
    same = uuid4()
    assert ValidationSubject.for_answer(same) == ValidationSubject.for_answer(same)
    assert ValidationSubject.for_answer(same) != ValidationSubject.for_variant(same)


def test_first_decision_starts_the_history() -> None:
    subject = ValidationSubject.for_qaset(uuid4())

    validation = Validation.start(
        subject, ValidationState.VALIDATED, actor_user_id=ALICE, at=T0, note="  Looks right "
    )

    assert validation.kind is ValidationKind.CLINICAL
    assert validation.current_state is ValidationState.VALIDATED
    [event] = validation.events
    assert (
        event.from_state,
        event.to_state,
        event.note,
        event.actor_user_id,
        event.occurred_at,
    ) == (
        None,
        ValidationState.VALIDATED,
        "Looks right",
        ALICE,
        T0,
    )


def test_redeciding_appends_and_flips_the_state() -> None:
    validation = Validation.start(
        ValidationSubject.for_audio(uuid4()), ValidationState.VALIDATED, actor_user_id=ALICE, at=T0
    )

    rejected = validation.decide(
        ValidationState.REJECTED, actor_user_id=BOB, at=T0 + timedelta(hours=1), note="Noisy"
    )
    validation.decide(ValidationState.VALIDATED, actor_user_id=ALICE, at=T0 + timedelta(hours=2))

    assert validation.current_state is ValidationState.VALIDATED
    assert [(e.from_state, e.to_state, e.actor_user_id) for e in validation.events] == [
        (None, ValidationState.VALIDATED, ALICE),
        (ValidationState.VALIDATED, ValidationState.REJECTED, BOB),
        (ValidationState.REJECTED, ValidationState.VALIDATED, ALICE),
    ]
    assert validation.events[1] == rejected
    assert rejected.note == "Noisy"
    assert [e.sequence for e in validation.events] == [1, 2, 3]


def test_blank_notes_are_dropped() -> None:
    validation = Validation.start(
        ValidationSubject.for_answer(uuid4()),
        ValidationState.REJECTED,
        actor_user_id=ALICE,
        at=T0,
        note="  ",
    )
    assert validation.events[0].note is None


def test_history_is_append_only() -> None:
    validation = Validation.start(
        ValidationSubject.for_variant(uuid4()),
        ValidationState.VALIDATED,
        actor_user_id=ALICE,
        at=T0,
    )
    events = validation.events
    validation.decide(ValidationState.REJECTED, actor_user_id=BOB, at=T0)
    assert len(events) == 1
    assert isinstance(validation.events, tuple)


def test_decisions_need_an_aware_time() -> None:
    with pytest.raises(InvalidValidationHistoryError):
        Validation.start(
            ValidationSubject.for_qaset(uuid4()),
            ValidationState.VALIDATED,
            actor_user_id=ALICE,
            at=datetime(2026, 10, 24),
        )


def test_rehydrate_checks_the_history_chain() -> None:
    validation = Validation.start(
        ValidationSubject.for_qaset(uuid4()), ValidationState.VALIDATED, actor_user_id=ALICE, at=T0
    )
    validation.decide(ValidationState.REJECTED, actor_user_id=BOB, at=T0)
    first, second = validation.events

    rebuilt = Validation(validation.id, validation.subject, [first, second])
    assert rebuilt.current_state is ValidationState.REJECTED

    for broken in (
        [],
        [second],
        [first, replace(second, from_state=ValidationState.REJECTED)],
        [first, replace(second, sequence=5)],
        [replace(first, from_state=ValidationState.REJECTED)],
    ):
        with pytest.raises(InvalidValidationHistoryError):
            Validation(validation.id, validation.subject, broken)


def test_reset_returns_to_pending_and_keeps_the_history() -> None:
    validation = Validation.start(
        ValidationSubject.for_qaset(uuid4()), ValidationState.VALIDATED, actor_user_id=ALICE, at=T0
    )
    before = validation.events

    event = validation.reset(actor_user_id=BOB, at=T0 + timedelta(minutes=5))

    assert event is not None
    assert validation.current_state is ValidationState.PENDING
    assert (event.from_state, event.to_state, event.actor_user_id, event.note) == (
        ValidationState.VALIDATED,
        ValidationState.PENDING,
        BOB,
        "content changed",
    )
    assert validation.events[: len(before)] == before
    assert [e.sequence for e in validation.events] == [1, 2]


def test_reset_of_a_pending_validation_is_a_no_op() -> None:
    validation = Validation.start(
        ValidationSubject.for_answer(uuid4()), ValidationState.REJECTED, actor_user_id=ALICE, at=T0
    )
    validation.reset(actor_user_id=BOB, at=T0)
    assert validation.reset(actor_user_id=BOB, at=T0) is None
    assert len(validation.events) == 2


def test_a_reset_validation_can_be_decided_again() -> None:
    validation = Validation.start(
        ValidationSubject.for_variant(uuid4()),
        ValidationState.VALIDATED,
        actor_user_id=ALICE,
        at=T0,
    )
    validation.reset(actor_user_id=BOB, at=T0)
    validation.decide(ValidationState.VALIDATED, actor_user_id=ALICE, at=T0)
    assert [(e.from_state, e.to_state) for e in validation.events] == [
        (None, ValidationState.VALIDATED),
        (ValidationState.VALIDATED, ValidationState.PENDING),
        (ValidationState.PENDING, ValidationState.VALIDATED),
    ]


def test_pending_is_reached_by_reset_only() -> None:
    with pytest.raises(InvalidDecisionError):
        parse_decision("pending")
    with pytest.raises(InvalidDecisionError):
        Validation.start(
            ValidationSubject.for_qaset(uuid4()),
            ValidationState.PENDING,
            actor_user_id=ALICE,
            at=T0,
        )
    validation = Validation.start(
        ValidationSubject.for_qaset(uuid4()), ValidationState.VALIDATED, actor_user_id=ALICE, at=T0
    )
    with pytest.raises(InvalidDecisionError):
        validation.decide(ValidationState.PENDING, actor_user_id=ALICE, at=T0)
