from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import insert, select, update

from qa_authoring.domain.model.prompt_template import PromptTemplate, PromptTemplateKey
from qa_authoring.infrastructure.persistence.schema.prompt_template import prompt_templates

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncConnection


def _to_domain(row: Any) -> PromptTemplate:
    return PromptTemplate(
        PromptTemplateKey(row.key),
        row.content,
        updated_by=row.updated_by,
        updated_at=row.updated_at,
    )


class PostgresPromptTemplateRepository:
    def __init__(self, connection: AsyncConnection) -> None:
        self._connection = connection

    async def get(self, key: PromptTemplateKey) -> PromptTemplate | None:
        row = (
            await self._connection.execute(
                select(prompt_templates).where(prompt_templates.c.key == key.value)
            )
        ).one_or_none()
        return None if row is None else _to_domain(row)

    async def list(self) -> tuple[PromptTemplate, ...]:
        rows = await self._connection.execute(select(prompt_templates))
        # Rows for keys no longer in the code are ignored, never served.
        known = [row for row in rows if row.key in PromptTemplateKey._value2member_map_]
        return tuple(sorted((_to_domain(row) for row in known), key=lambda t: t.key))

    async def add(self, template: PromptTemplate) -> None:
        await self._connection.execute(insert(prompt_templates).values(**self._row(template)))

    async def update(self, template: PromptTemplate) -> None:
        values = self._row(template)
        del values["key"]
        await self._connection.execute(
            update(prompt_templates)
            .where(prompt_templates.c.key == template.key.value)
            .values(**values)
        )

    @staticmethod
    def _row(template: PromptTemplate) -> dict[str, object]:
        return {
            "key": template.key.value,
            "content": template.content,
            "updated_by": template.updated_by,
            "updated_at": template.updated_at,
        }
