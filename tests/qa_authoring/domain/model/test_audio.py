from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from qa_authoring.domain.model.qaset import (
    AnswerNotFoundError,
    AudioAlreadyBoundError,
    AudioReference,
    InvalidAudioReferenceError,
    NoAudioError,
    QASet,
    QuestionVariant,
    QuestionVariantNotFoundError,
)

FR = uuid4()


def audio(**overrides: object) -> AudioReference:
    values: dict[str, object] = {
        "id": uuid4(),
        "storage_uri": "memory://abc",
        "mime_type": "audio/webm",
        "duration_ms": 1500,
        "checksum_sha256": "a" * 64,
        "size_bytes": 14549,
        "created_at": datetime(2026, 10, 24, tzinfo=UTC),
    }
    values.update(overrides)
    return AudioReference(**values)  # type: ignore[arg-type]


def _qaset() -> QASet:
    return QASet.create(theme_id=uuid4(), language_id=FR, answer_text="a")


@pytest.mark.parametrize(
    "overrides",
    [
        {"storage_uri": ""},
        {"mime_type": "webm"},
        {"mime_type": ""},
        {"duration_ms": -1},
        {"size_bytes": 0},
        {"checksum_sha256": "abc"},
        {"checksum_sha256": "A" * 64},
        {"checksum_sha256": "g" * 64},
        {"created_at": datetime(2026, 10, 24)},
    ],
)
def test_reference_values_are_validated(overrides: dict[str, object]) -> None:
    with pytest.raises(InvalidAudioReferenceError):
        audio(**overrides)


def test_answer_has_at_most_one_audio_and_set_replaces() -> None:
    qaset = _qaset()
    answer_id = qaset.presence(FR).answer.id
    first, second = audio(), audio()

    assert qaset.set_answer_audio(answer_id, first) is None
    assert qaset.set_answer_audio(answer_id, second) == first

    assert qaset.presence(FR).answer.audio == second
    assert qaset.audios == (second,)


def test_variant_audio_set_and_remove() -> None:
    qaset = _qaset()
    variant = qaset.add_variant(FR, "q")
    reference = audio()

    qaset.set_variant_audio(variant.id, reference)
    assert qaset.find_audio(reference.id) == reference
    assert qaset.remove_variant_audio(variant.id) == reference

    assert qaset.presence(FR).variants[0].audio is None
    assert qaset.find_audio(reference.id) is None
    with pytest.raises(NoAudioError):
        qaset.remove_variant_audio(variant.id)


def test_an_audio_is_bound_to_exactly_one_item() -> None:
    qaset = _qaset()
    variant = qaset.add_variant(FR, "q")
    reference = audio()
    qaset.set_answer_audio(qaset.presence(FR).answer.id, reference)

    with pytest.raises(AudioAlreadyBoundError):
        qaset.set_variant_audio(variant.id, reference)
    with pytest.raises(AudioAlreadyBoundError):
        qaset.set_variant_audio(variant.id, replace(reference))
    assert qaset.presence(FR).variants[0].audio is None


def test_items_must_belong_to_the_qaset() -> None:
    qaset = _qaset()
    with pytest.raises(AnswerNotFoundError):
        qaset.set_answer_audio(uuid4(), audio())
    with pytest.raises(QuestionVariantNotFoundError):
        qaset.set_variant_audio(uuid4(), audio())
    with pytest.raises(NoAudioError):
        qaset.remove_answer_audio(qaset.presence(FR).answer.id)


def test_removing_items_drops_their_audio() -> None:
    bm = uuid4()
    qaset = _qaset()
    qaset.add_language(bm, "b")
    variant = qaset.add_variant(bm, "q")
    qaset.set_variant_audio(variant.id, audio())
    qaset.set_answer_audio(qaset.presence(bm).answer.id, audio())
    kept = audio()
    qaset.set_answer_audio(qaset.presence(FR).answer.id, kept)

    qaset.remove_language(bm)

    assert qaset.audios == (kept,)


def test_rehydrate_rejects_one_audio_on_two_items() -> None:
    qaset = _qaset()
    variant = qaset.add_variant(FR, "q")
    reference = audio()
    qaset.set_answer_audio(qaset.presence(FR).answer.id, reference)
    answer = qaset.presence(FR).answer
    duplicated = QuestionVariant(variant.id, FR, "q", audio=reference)
    with pytest.raises(AudioAlreadyBoundError):
        QASet(qaset.id, qaset.theme_id, answers=(answer,), variants=(duplicated,))
