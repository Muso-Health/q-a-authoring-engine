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

    @field_validator("db_schema")
    @classmethod
    def _plain_identifier_not_public(cls, value: str) -> str:
        if not _SCHEMA_NAME.match(value) or value == "public":
            raise ValueError("db_schema must be a plain lowercase identifier other than 'public'")
        return value

    @property
    def use_cloud_sql_connector(self) -> bool:
        """Production wiring is selected by presence of the instance name — nothing else to set."""
        return bool(self.db_instance_connection_name)

    @property
    def cors_origins(self) -> list[str]:
        """The allowed origins as a list, split from the comma-separated env var; empty if unset."""
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]
