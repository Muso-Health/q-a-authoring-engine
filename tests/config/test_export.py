from __future__ import annotations

from typing import TYPE_CHECKING

from config.export import export_storage_from_settings
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
    local = export_storage_from_settings(
        _settings(monkeypatch, EXPORT_LOCAL_DIRECTORY=str(tmp_path))
    )
    gcs = export_storage_from_settings(
        _settings(monkeypatch, EXPORT_STORAGE_BACKEND="gcs", EXPORT_BUCKET="b")
    )
    assert isinstance(local, LocalBlobStorage)
    assert isinstance(gcs, GcsBlobStorage)
