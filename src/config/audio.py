from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from qa_authoring.application.audio_policy import AudioPolicy
from qa_authoring.infrastructure.audio.ffprobe import FfprobeAudioProbe
from qa_authoring.infrastructure.audio.gcs_storage import GcsAudioStorage
from qa_authoring.infrastructure.audio.local_storage import LocalAudioStorage

if TYPE_CHECKING:
    from config.settings import Settings
    from qa_authoring.application.ports.audio_probe import AudioProbePort
    from qa_authoring.application.ports.audio_storage import AudioStoragePort


def audio_storage_from_settings(settings: Settings) -> AudioStoragePort:
    if settings.audio_storage_backend == "gcs":
        return GcsAudioStorage(settings.audio_bucket, settings.audio_object_prefix)
    return LocalAudioStorage(Path(settings.audio_local_directory), settings.audio_object_prefix)


def audio_probe_from_settings(settings: Settings) -> AudioProbePort:
    return FfprobeAudioProbe(binary=settings.audio_ffprobe_path)


def audio_policy_from_settings(settings: Settings) -> AudioPolicy:
    return AudioPolicy(
        max_upload_bytes=settings.audio_max_upload_bytes,
        allowed_mime_types=settings.audio_mime_types,
        playback_url_ttl_seconds=settings.audio_playback_url_ttl_seconds,
    )
