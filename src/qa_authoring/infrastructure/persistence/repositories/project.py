from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import delete, exists, insert, select, update
from sqlalchemy.exc import IntegrityError

from qa_authoring.application.project_errors import (
    ProjectHasProtocolsError,
    UnknownBaseLanguageError,
)
from qa_authoring.domain.model.project import Project
from qa_authoring.infrastructure.persistence.repositories._integrity import (
    FOREIGN_KEY_VIOLATION,
    sqlstate,
)
from qa_authoring.infrastructure.persistence.schema.catalog import projects

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncConnection


def _to_domain(row: Any) -> Project:
    return Project(row.id, row.name, row.description, row.base_language_id)


class PostgresProjectRepository:
    def __init__(self, connection: AsyncConnection) -> None:
        self._connection = connection

    async def add(self, project: Project) -> None:
        try:
            await self._connection.execute(
                insert(projects).values(
                    id=project.id,
                    name=project.name,
                    description=project.description,
                    base_language_id=project.base_language_id,
                )
            )
        except IntegrityError as exc:
            if sqlstate(exc) == FOREIGN_KEY_VIOLATION:
                raise UnknownBaseLanguageError(project.base_language_id) from exc
            raise

    async def get(self, project_id: UUID) -> Project | None:
        row = (
            await self._connection.execute(select(projects).where(projects.c.id == project_id))
        ).one_or_none()
        return None if row is None else _to_domain(row)

    async def list(self) -> tuple[Project, ...]:
        rows = await self._connection.execute(
            select(projects).order_by(projects.c.name, projects.c.id)
        )
        return tuple(_to_domain(row) for row in rows)

    async def update(self, project: Project) -> None:
        await self._connection.execute(
            update(projects)
            .where(projects.c.id == project.id)
            .values(name=project.name, description=project.description)
        )

    async def delete(self, project_id: UUID) -> None:
        try:
            await self._connection.execute(delete(projects).where(projects.c.id == project_id))
        except IntegrityError as exc:
            if sqlstate(exc) == FOREIGN_KEY_VIOLATION:
                raise ProjectHasProtocolsError(project_id) from exc
            raise

    async def uses_base_language(self, language_id: UUID) -> bool:
        query = select(exists().where(projects.c.base_language_id == language_id))
        return bool(await self._connection.scalar(query))
