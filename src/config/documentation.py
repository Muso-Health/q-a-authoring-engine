from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from qa_authoring.application.documentation_policy import DocumentationPolicy
from qa_authoring.infrastructure.storage.gcs import GcsBlobStorage
from qa_authoring.infrastructure.storage.local import LocalBlobStorage

if TYPE_CHECKING:
    from config.settings import Settings
    from qa_authoring.application.ports.document_storage import DocumentStoragePort


def documentation_storage_from_settings(settings: Settings) -> DocumentStoragePort:
    if settings.documentation_storage_backend == "gcs":
        return GcsBlobStorage(settings.documentation_bucket, settings.documentation_object_prefix)
    return LocalBlobStorage(
        Path(settings.documentation_local_directory), settings.documentation_object_prefix
    )


def documentation_policy_from_settings(settings: Settings) -> DocumentationPolicy:
    return DocumentationPolicy(
        max_upload_bytes=settings.documentation_max_upload_bytes,
        allowed_mime_types=settings.documentation_mime_types,
        download_url_ttl_seconds=settings.documentation_download_url_ttl_seconds,
    )
