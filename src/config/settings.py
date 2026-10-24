from __future__ import annotations

import re

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# A plain lowercase Postgres identifier — the schema name is interpolated into DDL and search_path.
_SCHEMA_NAME = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")


class Settings(BaseSettings):
    """Environment-driven configuration (12-factor).

    Read from ``QA_AUTHORING_``-prefixed env vars or a local ``.env``. Local dev and the tests use
    the plain ``database_url``; production sets the Cloud SQL Connector fields instead
    (``db_instance_connection_name`` non-empty), and ``config.database`` selects the matching
    engine factory. A small pool (2-5) with ``pool_pre_ping``, a Cloud Run constraint.
    """

    model_config = SettingsConfigDict(env_prefix="QA_AUTHORING_", env_file=".env", extra="ignore")

    # Local / test connectivity: a plain asyncpg URL. Ignored when the Connector fields are set.
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/qa_authoring"
    db_pool_size: int = 5

    # Cloud SQL Python Connector (production). When ``db_instance_connection_name`` is non-empty the
    # engine is dialled through the Connector with password auth — the password comes from Secret
    # Manager (``QA_AUTHORING_DB_PASSWORD``), never the repo. ``db_ip_type`` is "public" (the
    # default, needs only roles/cloudsql.client) or "private" (needs Direct VPC egress).
    db_instance_connection_name: str = ""
    db_user: str = "qa_authoring_app"
    db_password: str = ""
    db_name: str = "qa_authoring"
    db_ip_type: str = "public"

    # The app's own schema (isolation: never mixed with other apps' tables). Every connection pins
    # it as ``search_path`` and Alembic keeps its version table there. ``public`` is refused.
    db_schema: str = "qa_authoring"

    # CORS — the browser origins allowed to call the API directly (the Angular SPA). Comma-separated
    # in the env var; empty disables CORS (same-origin / server-to-server, and the tests).
    cors_allowed_origins: str = ""

    # Audio recordings. "local" keeps blobs on the filesystem (dev/tests); "gcs" uses
    # ``audio_bucket``. Object keys are ``audio_object_prefix`` + the content's sha256. Uploads
    # are bounded by ``audio_max_upload_bytes`` and must probe as one of the comma-separated
    # ``audio_allowed_mime_types``. ``audio_ffprobe_path`` locates ffprobe (from ffmpeg).
    audio_storage_backend: str = "local"
    audio_bucket: str = ""
    audio_object_prefix: str = "audio/"
    audio_local_directory: str = ".audio-storage"
    audio_playback_url_ttl_seconds: int = 900
    audio_max_upload_bytes: int = 10 * 1024 * 1024
    audio_allowed_mime_types: str = "audio/webm,audio/ogg,audio/wav,audio/mpeg,audio/mp4"
    audio_ffprobe_path: str = "ffprobe"

    # Authentication. "iap" verifies Google IAP's signed assertion for ``auth_iap_audience``
    # (required then); "dev" trusts a plain X-Dev-User header and must never face the internet.
    # ``bootstrap_admin_email``, when set, is ensured an active admin holding every permission
    # at startup.
    auth_provider: str = "iap"
    auth_iap_audience: str = ""
    bootstrap_admin_email: str = ""

    @field_validator("db_schema")
    @classmethod
    def _plain_identifier_not_public(cls, value: str) -> str:
        if not _SCHEMA_NAME.match(value) or value == "public":
            raise ValueError("db_schema must be a plain lowercase identifier other than 'public'")
        return value

    @field_validator("audio_storage_backend")
    @classmethod
    def _known_audio_backend(cls, value: str) -> str:
        if value not in {"local", "gcs"}:
            raise ValueError("audio_storage_backend must be 'local' or 'gcs'")
        return value

    @field_validator("auth_provider")
    @classmethod
    def _known_auth_provider(cls, value: str) -> str:
        if value not in {"iap", "dev"}:
            raise ValueError("auth_provider must be 'iap' or 'dev'")
        return value

    @property
    def audio_mime_types(self) -> frozenset[str]:
        return frozenset(m.strip() for m in self.audio_allowed_mime_types.split(",") if m.strip())

    @property
    def use_cloud_sql_connector(self) -> bool:
        """Production wiring is selected by presence of the instance name — nothing else to set."""
        return bool(self.db_instance_connection_name)

    @property
    def cors_origins(self) -> list[str]:
        """The allowed origins as a list, split from the comma-separated env var; empty if unset."""
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]
