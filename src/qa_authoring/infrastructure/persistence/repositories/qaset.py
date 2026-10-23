from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any

from sqlalchemy import Table, delete, exists, insert, select, update
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
    from collections.abc import Iterable, Sequence
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncConnection


class PostgresQASetRepository:
    """Persists the QASet aggregate across ``qasets``, ``answers`` and ``question_variants``.

    ``save`` diffs the aggregate against the stored child rows (delete removed, insert new, update
    changed text), so surviving rows keep their ``created_at``. Children load in creation order
    (``created_at`` then ``id``), which is the order the aggregate keeps them in.
    """

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
        await self._insert(answers, qaset.id, qaset.answers)
        await self._insert(question_variants, qaset.id, qaset.variants)

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
        stored_variants = await self._stored_texts(question_variants, qaset.id)
        stored_answers = await self._stored_texts(answers, qaset.id)
        # Variants first: a removed answer's variants go with it (composite FK cascade), and a
        # language re-added in the same save must not collide with its old answer row.
        await self._delete_missing(question_variants, stored_variants, qaset.variants)
        await self._delete_missing(answers, stored_answers, qaset.answers)
        await self._insert(
            answers, qaset.id, [a for a in qaset.answers if a.id not in stored_answers]
        )
        await self._insert(
            question_variants, qaset.id, [v for v in qaset.variants if v.id not in stored_variants]
        )
        await self._update_changed(answers, stored_answers, qaset.answers)
        await self._update_changed(question_variants, stored_variants, qaset.variants)

    async def delete(self, qaset_id: UUID) -> None:
        await self._connection.execute(delete(qasets).where(qasets.c.id == qaset_id))

    async def exists_for_theme(self, theme_id: UUID) -> bool:
        query = select(exists().where(qasets.c.theme_id == theme_id))
        return bool(await self._connection.scalar(query))

    async def uses_language(self, language_id: UUID) -> bool:
        # Every variant's language has an answer (composite FK), so answers are enough.
        query = select(exists().where(answers.c.language_id == language_id))
        return bool(await self._connection.scalar(query))

    async def _stored_texts(self, table: Table, qaset_id: UUID) -> dict[UUID, str]:
        rows = await self._connection.execute(
            select(table.c.id, table.c.text).where(table.c.qaset_id == qaset_id)
        )
        return {row.id: row.text for row in rows}

    async def _delete_missing(
        self, table: Table, stored: dict[UUID, str], current: Iterable[Answer | QuestionVariant]
    ) -> None:
        missing = stored.keys() - {child.id for child in current}
        if missing:
            await self._connection.execute(delete(table).where(table.c.id.in_(missing)))

    async def _update_changed(
        self, table: Table, stored: dict[UUID, str], current: Iterable[Answer | QuestionVariant]
    ) -> None:
        for child in current:
            if child.id in stored and stored[child.id] != child.text:
                await self._connection.execute(
                    update(table).where(table.c.id == child.id).values(text=child.text)
                )

    async def _insert(
        self, table: Table, qaset_id: UUID, children: Sequence[Answer | QuestionVariant]
    ) -> None:
        if not children:
            return
        rows = [
            {"id": c.id, "qaset_id": qaset_id, "language_id": c.language_id, "text": c.text}
            for c in children
        ]
        try:
            await self._connection.execute(insert(table), rows)
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
        for a in await self._connection.execute(
            select(answers)
            .where(answers.c.qaset_id.in_(ids))
            .order_by(answers.c.created_at, answers.c.id)
        ):
            answers_by_qaset[a.qaset_id].append(Answer(a.id, a.language_id, a.text))
        variants_by_qaset: defaultdict[UUID, list[QuestionVariant]] = defaultdict(list)
        for v in await self._connection.execute(
            select(question_variants)
            .where(question_variants.c.qaset_id.in_(ids))
            .order_by(question_variants.c.created_at, question_variants.c.id)
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
