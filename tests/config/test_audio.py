from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from config.audio import audio_policy_from_settings, audio_storage_from_settings
from config.settings import Settings
from qa_authoring.infrastructure.storage.gcs import GcsBlobStorage
from qa_authoring.infrastructure.storage.local import LocalBlobStorage

if TYPE_CHECKING:
    from pathlib import Path


def _settings(monkeypatch: pytest.MonkeyPatch, **env: str) -> Settings:
    for key, value in env.items():
        monkeypatch.setenv(f"QA_AUTHORING_{key}", value)
    return Settings(_env_file=None)  # type: ignore[call-arg]


def test_local_storage_is_selected_by_default(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    storage = audio_storage_from_settings(
        _settings(monkeypatch, AUDIO_LOCAL_DIRECTORY=str(tmp_path))
    )
    assert isinstance(storage, LocalBlobStorage)


def test_gcs_storage_is_selected_by_config(monkeypatch: pytest.MonkeyPatch) -> None:
    storage = audio_storage_from_settings(
        _settings(monkeypatch, AUDIO_STORAGE_BACKEND="gcs", AUDIO_BUCKET="qa-audio")
    )
    assert isinstance(storage, GcsBlobStorage)


def test_gcs_storage_needs_a_bucket(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ValueError, match="bucket"):
        audio_storage_from_settings(_settings(monkeypatch, AUDIO_STORAGE_BACKEND="gcs"))


def test_policy_from_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    policy = audio_policy_from_settings(
        _settings(
            monkeypatch,
            AUDIO_MAX_UPLOAD_BYTES="10",
            AUDIO_ALLOWED_MIME_TYPES="audio/wav",
            AUDIO_PLAYBACK_URL_TTL_SECONDS="30",
        )
    )
    assert (
        policy.max_upload_bytes,
        policy.allowed_mime_types,
        policy.playback_url_ttl_seconds,
    ) == (
        10,
        frozenset({"audio/wav"}),
        30,
    )
