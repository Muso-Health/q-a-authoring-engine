from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.infrastructure.persistence.engine import (
    CloudSqlEngineFactory,
    EngineFactory,
    LocalDsnEngineFactory,
)

if TYPE_CHECKING:
    from config.settings import Settings


def engine_factory_from_settings(settings: Settings) -> EngineFactory:
    """Pick the connection strategy from config — the one place that knows both exist."""
    if settings.use_cloud_sql_connector:
        return CloudSqlEngineFactory(
            instance_connection_name=settings.db_instance_connection_name,
            user=settings.db_user,
            password=settings.db_password,
            db=settings.db_name,
            schema=settings.db_schema,
            ip_type=settings.db_ip_type,
            pool_size=settings.db_pool_size,
        )
    return LocalDsnEngineFactory(
        database_url=settings.database_url,
        schema=settings.db_schema,
        pool_size=settings.db_pool_size,
    )
