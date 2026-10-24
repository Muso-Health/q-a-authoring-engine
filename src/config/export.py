from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from qa_authoring.infrastructure.storage.gcs import GcsBlobStorage
from qa_authoring.infrastructure.storage.local import LocalBlobStorage

if TYPE_CHECKING:
    from config.settings import Settings
    from qa_authoring.application.ports.export_storage import ExportStoragePort


def export_storage_from_settings(settings: Settings) -> ExportStoragePort:
    if settings.export_storage_backend == "gcs":
        return GcsBlobStorage(settings.export_bucket, settings.export_object_prefix)
    return LocalBlobStorage(Path(settings.export_local_directory), settings.export_object_prefix)
