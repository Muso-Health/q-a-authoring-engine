from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any

from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.exc import IntegrityError

from qa_authoring.application.qaset_errors import UnknownLanguageError
from qa_authoring.domain.model.glossary import GlossaryForm, GlossaryStatus, GlossaryTerm
from qa_authoring.domain.value_objects.naming import search_fold
from qa_authoring.infrastructure.persistence.repositories._integrity import (
    FOREIGN_KEY_VIOLATION,
    sqlstate,
)
from qa_authoring.infrastructure.persistence.schema.glossary import glossary_forms, glossary_terms

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from sqlalchemy import Select
    from sqlalchemy.ext.asyncio import AsyncConnection


def _term_values(term: GlossaryTerm) -> dict[str, Any]:
    return {
        "label": term.label,
        "note": term.note,
        "status": term.status.value,
        "search_text": term.search_text,
        "created_at": term.created_at,
        "updated_at": term.updated_at,
    }


def _form_values(form: GlossaryForm) -> dict[str, Any]:
    return {
        "id": form.id,
        "term_id": form.term_id,
        "language_id": form.language_id,
        "preferred": form.preferred,
        "synonyms": list(form.synonyms),
        "avoid": list(form.avoid),
        "note": form.note,
    }


class PostgresGlossaryRepository:
    def __init__(self, connection: AsyncConnection) -> None:
        self._connection = connection

    async def add(self, term: GlossaryTerm) -> None:
        await self._connection.execute(
            insert(glossary_terms).values(id=term.id, **_term_values(term))
        )
        await self._insert_forms(term)

    async def get(self, term_id: UUID) -> GlossaryTerm | None:
        return await self._one(select(glossary_terms).where(glossary_terms.c.id == term_id))

    async def get_for_update(self, term_id: UUID) -> GlossaryTerm | None:
        query = select(glossary_terms).where(glossary_terms.c.id == term_id).with_for_update()
        return await self._one(query)

    async def save(self, term: GlossaryTerm) -> None:
        await self._connection.execute(
            update(glossary_terms)
            .where(glossary_terms.c.id == term.id)
            .values(**_term_values(term))
        )
        # The term is locked by its handler, so replacing its forms cannot race another edit.
        await self._connection.execute(
            delete(glossary_forms).where(glossary_forms.c.term_id == term.id)
        )
        await self._insert_forms(term)

    async def list(
        self, *, status: GlossaryStatus | None, search: str | None, limit: int, offset: int
    ) -> tuple[tuple[GlossaryTerm, ...], int]:
        conditions = []
        if status is not None:
            conditions.append(glossary_terms.c.status == status.value)
        if search is not None:
            conditions.append(
                glossary_terms.c.search_text.contains(search_fold(search), autoescape=True)
            )
        total = await self._connection.scalar(
            select(func.count()).select_from(glossary_terms).where(*conditions)
        )
        page = (
            select(glossary_terms)
            .where(*conditions)
            .order_by(func.lower(glossary_terms.c.label), glossary_terms.c.id)
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._connection.execute(page)).all()
        return await self._with_forms(rows), int(total or 0)

    async def _insert_forms(self, term: GlossaryTerm) -> None:
        if not term.forms:
            return
        try:
            await self._connection.execute(
                insert(glossary_forms), [_form_values(f) for f in term.forms]
            )
        except IntegrityError as exc:
            if sqlstate(exc) == FOREIGN_KEY_VIOLATION:
                raise UnknownLanguageError(None) from exc
            raise

    async def _one(self, query: Select[Any]) -> GlossaryTerm | None:
        row = (await self._connection.execute(query)).one_or_none()
        if row is None:
            return None
        [term] = await self._with_forms([row])
        return term

    async def _with_forms(self, rows: Sequence[Any]) -> tuple[GlossaryTerm, ...]:
        forms: dict[UUID, list[GlossaryForm]] = defaultdict(list)
        if rows:
            form_rows = await self._connection.execute(
                select(glossary_forms).where(glossary_forms.c.term_id.in_([r.id for r in rows]))
            )
            for f in form_rows:
                forms[f.term_id].append(
                    GlossaryForm(
                        f.id, f.term_id, f.language_id, f.preferred, f.synonyms, f.avoid, f.note
                    )
                )
        return tuple(
            GlossaryTerm(
                r.id,
                r.label,
                r.note,
                GlossaryStatus(r.status),
                r.created_at,
                r.updated_at,
                forms[r.id],
            )
            for r in rows
        )
