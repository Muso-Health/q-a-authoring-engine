from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any

from sqlalchemy import delete, exists, insert, select
from sqlalchemy.exc import IntegrityError

from qa_authoring.application.qaset_errors import UnknownLanguageError
from qa_authoring.application.theme_errors import ThemeNotFoundError
from qa_authoring.domain.model.qaset import Answer, QASet, QuestionVariant
from qa_authoring.infrastructure.persistence.repositories._integrity import (
    FOREIGN_KEY_VIOLATION,
    constraint_name,
    sqlstate,
)
from qa_authoring.infrastructure.persistence.schema.qaset import (
    answers,
    qasets,
    question_variants,
)

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncConnection


class PostgresQASetRepository:
    """Persists the QASet aggregate across ``qasets``, ``answers`` and ``question_variants``.
    ``save`` rewrites the aggregate's child rows, so the stored state always equals the root's."""

    def __init__(self, connection: AsyncConnection) -> None:
        self._connection = connection

    async def add(self, qaset: QASet) -> None:
        try:
            await self._connection.execute(
                insert(qasets).values(id=qaset.id, theme_id=qaset.theme_id)
            )
        except IntegrityError as exc:
            if sqlstate(exc) == FOREIGN_KEY_VIOLATION:
                raise ThemeNotFoundError(qaset.theme_id) from exc
            raise
        await self._insert_children(qaset)

    async def get(self, qaset_id: UUID) -> QASet | None:
        row = (
            await self._connection.execute(select(qasets).where(qasets.c.id == qaset_id))
        ).one_or_none()
        if row is None:
            return None
        [qaset] = await self._hydrate([row])
        return qaset

    async def list_by_theme(self, theme_id: UUID) -> tuple[QASet, ...]:
        rows = (
            await self._connection.execute(
                select(qasets).where(qasets.c.theme_id == theme_id).order_by(qasets.c.id)
            )
        ).all()
        return await self._hydrate(rows)

    async def save(self, qaset: QASet) -> None:
        await self._connection.execute(
            delete(question_variants).where(question_variants.c.qaset_id == qaset.id)
        )
        await self._connection.execute(delete(answers).where(answers.c.qaset_id == qaset.id))
        await self._insert_children(qaset)

    async def delete(self, qaset_id: UUID) -> None:
        await self._connection.execute(delete(qasets).where(qasets.c.id == qaset_id))

    async def exists_for_theme(self, theme_id: UUID) -> bool:
        query = select(exists().where(qasets.c.theme_id == theme_id))
        return bool(await self._connection.scalar(query))

    async def uses_language(self, language_id: UUID) -> bool:
        # Every variant's language has an answer (composite FK), so answers are enough.
        query = select(exists().where(answers.c.language_id == language_id))
        return bool(await self._connection.scalar(query))

    async def _insert_children(self, qaset: QASet) -> None:
        try:
            await self._connection.execute(
                insert(answers),
                [
                    {"id": a.id, "qaset_id": qaset.id, "language_id": a.language_id, "text": a.text}
                    for a in qaset.answers
                ],
            )
            if qaset.variants:
                await self._connection.execute(
                    insert(question_variants),
                    [
                        {
                            "id": v.id,
                            "qaset_id": qaset.id,
                            "language_id": v.language_id,
                            "text": v.text,
                        }
                        for v in qaset.variants
                    ],
                )
        except IntegrityError as exc:
            if sqlstate(exc) == FOREIGN_KEY_VIOLATION and (constraint_name(exc) or "").endswith(
                "_language_id_languages"
            ):
                raise UnknownLanguageError(None) from exc
            raise

    async def _hydrate(self, rows: Sequence[Any]) -> tuple[QASet, ...]:
        if not rows:
            return ()
        ids = [row.id for row in rows]
        answers_by_qaset: defaultdict[UUID, list[Answer]] = defaultdict(list)
        for a in await self._connection.execute(select(answers).where(answers.c.qaset_id.in_(ids))):
            answers_by_qaset[a.qaset_id].append(Answer(a.id, a.language_id, a.text))
        variants_by_qaset: defaultdict[UUID, list[QuestionVariant]] = defaultdict(list)
        for v in await self._connection.execute(
            select(question_variants).where(question_variants.c.qaset_id.in_(ids))
        ):
            variants_by_qaset[v.qaset_id].append(QuestionVariant(v.id, v.language_id, v.text))
        return tuple(
            QASet(
                row.id,
                row.theme_id,
                answers=answers_by_qaset[row.id],
                variants=variants_by_qaset[row.id],
            )
            for row in rows
        )
