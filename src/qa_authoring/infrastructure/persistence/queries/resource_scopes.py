from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import func, literal, select

from qa_authoring.application.ports.resource_scopes import ResourceKind, ResourceScope
from qa_authoring.infrastructure.persistence.schema.catalog import projects, protocols, themes
from qa_authoring.infrastructure.persistence.schema.documentation import documentation
from qa_authoring.infrastructure.persistence.schema.qaset import (
    answers,
    audios,
    qasets,
    question_variants,
)

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy import Select
    from sqlalchemy.ext.asyncio import AsyncConnection

_NO_LANGUAGE = literal(None).label("language_id")


def _theme_scope(theme_id: Any) -> Select[Any]:
    return (
        select(protocols.c.project_id, _NO_LANGUAGE)
        .select_from(themes.join(protocols, protocols.c.id == themes.c.protocol_id))
        .where(themes.c.id == theme_id)
    )


def _query(kind: ResourceKind, resource_id: UUID) -> Select[Any]:
    """(project_id, language_id) of one resource, walking up to its project."""
    if kind is ResourceKind.PROJECT:
        return select(projects.c.id, _NO_LANGUAGE).where(projects.c.id == resource_id)
    if kind is ResourceKind.PROTOCOL:
        return select(protocols.c.project_id, _NO_LANGUAGE).where(protocols.c.id == resource_id)
    if kind is ResourceKind.THEME:
        return _theme_scope(resource_id)
    if kind is ResourceKind.DOCUMENTATION:
        theme = select(documentation.c.theme_id).where(documentation.c.id == resource_id)
        return _theme_scope(theme.scalar_subquery())
    if kind is ResourceKind.QASET:
        theme = select(qasets.c.theme_id).where(qasets.c.id == resource_id)
        return _theme_scope(theme.scalar_subquery())
    if kind is ResourceKind.ANSWER or kind is ResourceKind.VARIANT:
        item = answers if kind is ResourceKind.ANSWER else question_variants
        return (
            select(protocols.c.project_id, item.c.language_id)
            .select_from(
                item.join(qasets, qasets.c.id == item.c.qaset_id)
                .join(themes, themes.c.id == qasets.c.theme_id)
                .join(protocols, protocols.c.id == themes.c.protocol_id)
            )
            .where(item.c.id == resource_id)
        )
    qv = question_variants
    return (
        select(protocols.c.project_id, func.coalesce(answers.c.language_id, qv.c.language_id))
        .select_from(
            audios.outerjoin(answers, answers.c.id == audios.c.answer_id)
            .outerjoin(qv, qv.c.id == audios.c.variant_id)
            .join(qasets, qasets.c.id == func.coalesce(answers.c.qaset_id, qv.c.qaset_id))
            .join(themes, themes.c.id == qasets.c.theme_id)
            .join(protocols, protocols.c.id == themes.c.protocol_id)
        )
        .where(audios.c.id == resource_id)
    )


class PostgresResourceScopes:
    def __init__(self, connection: AsyncConnection) -> None:
        self._connection = connection

    async def resolve(self, kind: ResourceKind, resource_id: UUID) -> ResourceScope | None:
        row = (await self._connection.execute(_query(kind, resource_id))).first()
        return None if row is None else ResourceScope(row[0], row[1])
