from __future__ import annotations

from typing import TYPE_CHECKING

from config.documentation import (
    documentation_policy_from_settings,
    documentation_storage_from_settings,
)
from config.settings import Settings
from qa_authoring.infrastructure.storage.gcs import GcsBlobStorage
from qa_authoring.infrastructure.storage.local import LocalBlobStorage

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def _settings(monkeypatch: pytest.MonkeyPatch, **env: str) -> Settings:
    for key, value in env.items():
        monkeypatch.setenv(f"QA_AUTHORING_{key}", value)
    return Settings(_env_file=None)  # type: ignore[call-arg]


def test_storage_backend_selection(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    local = documentation_storage_from_settings(
        _settings(monkeypatch, DOCUMENTATION_LOCAL_DIRECTORY=str(tmp_path))
    )
    gcs = documentation_storage_from_settings(
        _settings(monkeypatch, DOCUMENTATION_STORAGE_BACKEND="gcs", DOCUMENTATION_BUCKET="b")
    )
    assert isinstance(local, LocalBlobStorage)
    assert isinstance(gcs, GcsBlobStorage)


def test_policy(monkeypatch: pytest.MonkeyPatch) -> None:
    policy = documentation_policy_from_settings(
        _settings(
            monkeypatch,
            DOCUMENTATION_MAX_UPLOAD_BYTES="10",
            DOCUMENTATION_ALLOWED_MIME_TYPES="text/plain",
        )
    )
    assert (policy.max_upload_bytes, policy.allowed_mime_types) == (10, frozenset({"text/plain"}))
