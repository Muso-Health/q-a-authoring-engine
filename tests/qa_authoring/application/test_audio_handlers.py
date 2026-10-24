from __future__ import annotations

import hashlib
from datetime import timedelta
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest

from qa_authoring.application.audio_errors import (
    AudioNotFoundError,
    AudioTooLargeError,
    UnsupportedAudioTypeError,
)
from qa_authoring.application.delete_answer_audio.command import DeleteAnswerAudioCommand
from qa_authoring.application.delete_variant_audio.command import DeleteVariantAudioCommand
from qa_authoring.application.get_audio.command import GetAudioQuery
from qa_authoring.application.get_audio_playback_url.command import GetAudioPlaybackUrlQuery
from qa_authoring.application.qaset_errors import QASetNotFoundError
from qa_authoring.application.set_answer_audio.command import SetAnswerAudioCommand
from qa_authoring.application.set_variant_audio.command import SetVariantAudioCommand
from qa_authoring.domain.model.qaset import (
    AnswerNotFoundError,
    NoAudioError,
    QASet,
    QuestionVariantNotFoundError,
)
from tests.fakes import NOW, in_memory_container

if TYPE_CHECKING:
    from config.container import Container
    from qa_authoring.application.audio_response import AudioResult
    from tests.fakes import InMemoryStore

FR = uuid4()
SOUND = b"RIFF fake sound"


def _uri(content: bytes) -> str:
    return f"memory://audio/{hashlib.sha256(content).hexdigest()}"


@pytest.fixture
def world() -> tuple[Container, InMemoryStore, QASet]:
    container, store = in_memory_container()
    qaset = QASet.create(theme_id=uuid4(), language_id=FR, answer_text="a")
    qaset.add_variant(FR, "q")
    store.qasets.rows[qaset.id] = qaset
    return container, store, qaset


async def _set_answer(
    container: Container, qaset: QASet, content: bytes = SOUND, answer_id: UUID | None = None
) -> tuple[AudioResult, bool]:
    command = SetAnswerAudioCommand(
        qaset_id=qaset.id,
        answer_id=answer_id or qaset.answers[0].id,
        content=content,
        client_mime="audio/webm;codecs=opus",
    )
    return await container.run(container.build_set_answer_audio, command)


async def _set_variant(
    container: Container, qaset: QASet, content: bytes = SOUND
) -> tuple[AudioResult, bool]:
    command = SetVariantAudioCommand(
        qaset_id=qaset.id, variant_id=qaset.variants[0].id, content=content, client_mime=None
    )
    return await container.run(container.build_set_variant_audio, command)


async def test_set_answer_audio_computes_metadata_from_the_bytes(
    world: tuple[Container, InMemoryStore, QASet],
) -> None:
    container, store, qaset = world

    result, created = await _set_answer(container, qaset)

    assert created is True
    assert result.checksum_sha256 == hashlib.sha256(SOUND).hexdigest()
    assert result.size_bytes == len(SOUND)
    assert (result.duration_ms, result.mime_type, result.created_at) == (1500, "audio/webm", NOW)
    assert store.audio_storage.blobs == {_uri(SOUND): SOUND}
    stored = store.qasets.rows[qaset.id].answers[0].audio
    assert stored is not None
    assert (stored.id, stored.storage_uri) == (result.id, _uri(SOUND))


async def test_storage_happens_before_the_database(
    world: tuple[Container, InMemoryStore, QASet],
) -> None:
    container, store, qaset = world
    await _set_answer(container, qaset)
    assert store.events == [f"store {_uri(SOUND)}", "save", "commit"]


async def test_a_database_failure_after_upload_commits_no_reference(
    world: tuple[Container, InMemoryStore, QASet],
) -> None:
    container, store, qaset = world
    store.qasets.fail_next_save = True

    with pytest.raises(RuntimeError):
        await _set_answer(container, qaset)

    # Upload happened first; the reference was never committed, so nothing points at a missing
    # blob. The orphan blob is tolerated (content-addressed, idempotent) and not deleted, since
    # another reference could share the same content.
    assert store.events == [f"store {_uri(SOUND)}", "rollback"]
    assert store.qasets.rows[qaset.id].answers[0].audio is None
    assert _uri(SOUND) in store.audio_storage.blobs


async def test_replace_deletes_the_old_blob_after_commit(
    world: tuple[Container, InMemoryStore, QASet],
) -> None:
    container, store, qaset = world
    first, _ = await _set_answer(container, qaset, b"first sound")
    store.events.clear()

    second, created = await _set_answer(container, qaset, b"second sound")

    assert created is False
    assert second.id != first.id
    assert store.events == [
        f"store {_uri(b'second sound')}",
        "save",
        "commit",
        f"delete {_uri(b'first sound')}",
    ]
    assert set(store.audio_storage.blobs) == {_uri(b"second sound")}
    stored = store.qasets.rows[qaset.id].answers[0].audio
    assert stored is not None
    assert stored.id == second.id


async def test_replace_keeps_a_blob_still_used_elsewhere(
    world: tuple[Container, InMemoryStore, QASet],
) -> None:
    container, store, qaset = world
    await _set_answer(container, qaset, SOUND)
    await _set_variant(container, qaset, SOUND)  # same bytes, same content-addressed blob
    store.events.clear()

    await _set_answer(container, qaset, b"other sound")

    assert not any(event.startswith("delete") for event in store.events)
    assert _uri(SOUND) in store.audio_storage.blobs


async def test_replace_with_identical_bytes_keeps_the_blob(
    world: tuple[Container, InMemoryStore, QASet],
) -> None:
    container, store, qaset = world
    await _set_answer(container, qaset)
    await _set_answer(container, qaset)
    assert store.audio_storage.blobs == {_uri(SOUND): SOUND}


async def test_mime_whitelist_and_size_are_enforced_before_storage(
    world: tuple[Container, InMemoryStore, QASet],
) -> None:
    container, store, qaset = world
    with pytest.raises(AudioTooLargeError):
        await _set_answer(container, qaset, b"x" * 65)
    with pytest.raises(UnsupportedAudioTypeError):
        await _set_answer(container, qaset, b"junk bytes")
    with pytest.raises(UnsupportedAudioTypeError):
        await _set_answer(container, qaset, b"")
    store.audio_probe.mime_type = "audio/mpeg"
    with pytest.raises(UnsupportedAudioTypeError):
        await _set_answer(container, qaset)
    assert store.audio_storage.blobs == {}
    assert store.qasets.rows[qaset.id].audios == ()


async def test_targets_are_validated_before_storage(
    world: tuple[Container, InMemoryStore, QASet],
) -> None:
    container, store, qaset = world
    with pytest.raises(AnswerNotFoundError):
        await _set_answer(container, qaset, answer_id=uuid4())
    with pytest.raises(QuestionVariantNotFoundError):
        await container.run(
            container.build_set_variant_audio,
            SetVariantAudioCommand(
                qaset_id=qaset.id, variant_id=uuid4(), content=SOUND, client_mime=None
            ),
        )
    with pytest.raises(QASetNotFoundError):
        await container.run(
            container.build_set_answer_audio,
            SetAnswerAudioCommand(
                qaset_id=uuid4(), answer_id=uuid4(), content=SOUND, client_mime=None
            ),
        )
    assert store.audio_storage.blobs == {}


async def test_delete_removes_the_reference_then_the_blob(
    world: tuple[Container, InMemoryStore, QASet],
) -> None:
    container, store, qaset = world
    await _set_variant(container, qaset)
    store.events.clear()

    await container.run(
        container.build_delete_variant_audio,
        DeleteVariantAudioCommand(qaset_id=qaset.id, variant_id=qaset.variants[0].id),
    )

    assert store.events == ["save", "commit", f"delete {_uri(SOUND)}"]
    assert store.qasets.rows[qaset.id].variants[0].audio is None
    assert store.audio_storage.blobs == {}
    with pytest.raises(NoAudioError):
        await container.run(
            container.build_delete_variant_audio,
            DeleteVariantAudioCommand(qaset_id=qaset.id, variant_id=qaset.variants[0].id),
        )


async def test_delete_answer_audio(world: tuple[Container, InMemoryStore, QASet]) -> None:
    container, store, qaset = world
    await _set_answer(container, qaset)
    await container.run(
        container.build_delete_answer_audio,
        DeleteAnswerAudioCommand(qaset_id=qaset.id, answer_id=qaset.answers[0].id),
    )
    assert store.qasets.rows[qaset.id].audios == ()
    assert store.audio_storage.blobs == {}


async def test_get_audio_and_playback_url(world: tuple[Container, InMemoryStore, QASet]) -> None:
    container, _, qaset = world
    created, _ = await _set_answer(container, qaset)

    assert await container.run(container.build_get_audio, GetAudioQuery(created.id)) == created
    playback = await container.run(
        container.build_get_audio_playback_url, GetAudioPlaybackUrlQuery(created.id)
    )

    assert playback.url == f"https://signed.example/audio/{created.checksum_sha256}?ttl=300"
    assert playback.expires_at == NOW + timedelta(seconds=300)
    with pytest.raises(AudioNotFoundError):
        await container.run(container.build_get_audio, GetAudioQuery(uuid4()))
    with pytest.raises(AudioNotFoundError):
        await container.run(
            container.build_get_audio_playback_url, GetAudioPlaybackUrlQuery(uuid4())
        )
