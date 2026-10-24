from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any

from sqlalchemy import Text, and_, case, func, literal, select, tuple_, union_all

from qa_authoring.application.validation_queues import (
    AudioQueueItem,
    ClinicalQueueItem,
    NamedRef,
    QueueContext,
    QueuePage,
    QueueState,
    SourceText,
    TranslationQueueItem,
)
from qa_authoring.domain.model.validation import ValidationState
from qa_authoring.infrastructure.persistence.schema.catalog import projects, protocols, themes
from qa_authoring.infrastructure.persistence.schema.language import languages
from qa_authoring.infrastructure.persistence.schema.qaset import (
    answer_translation_links,
    answers,
    audios,
    qasets,
    question_variants,
    variant_translation_links,
)
from qa_authoring.infrastructure.persistence.schema.validation import validations

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from sqlalchemy import ColumnElement, FromClause, Select, Table
    from sqlalchemy.ext.asyncio import AsyncConnection

    from qa_authoring.application.validation_queues import QueueFilter

_PENDING = ValidationState.PENDING.value

_CONTEXT = (
    projects.c.id.label("project_id"),
    projects.c.name.label("project_name"),
    protocols.c.id.label("protocol_id"),
    protocols.c.name.label("protocol_name"),
    themes.c.id.label("theme_id"),
    themes.c.name.label("theme_name"),
    projects.c.base_language_id.label("base_language_id"),
)


def _within_context(source: FromClause, qaset_id: ColumnElement[Any]) -> FromClause:
    return (
        source.join(qasets, qasets.c.id == qaset_id)
        .join(themes, themes.c.id == qasets.c.theme_id)
        .join(protocols, protocols.c.id == themes.c.protocol_id)
        .join(projects, projects.c.id == protocols.c.project_id)
    )


def _context(row: Any) -> QueueContext:
    return QueueContext(
        NamedRef(row.project_id, row.project_name),
        NamedRef(row.protocol_id, row.protocol_name),
        NamedRef(row.theme_id, row.theme_name),
    )


def _state(current_state: ColumnElement[Any]) -> ColumnElement[str]:
    """Never decided upon counts as pending."""
    return func.coalesce(current_state, _PENDING)


def _conditions(queue_filter: QueueFilter, state: ColumnElement[str]) -> list[ColumnElement[bool]]:
    conditions: list[ColumnElement[bool]] = []
    if queue_filter.project_id is not None:
        conditions.append(projects.c.id == queue_filter.project_id)
    if queue_filter.theme_id is not None:
        conditions.append(themes.c.id == queue_filter.theme_id)
    if queue_filter.state is not QueueState.ALL:
        conditions.append(state == queue_filter.state.value)
    return conditions


class PostgresValidationQueues:
    """Set-based SQL over the stored rows: a few queries per page, no aggregate is loaded."""

    def __init__(self, connection: AsyncConnection) -> None:
        self._connection = connection

    async def clinical(self, queue_filter: QueueFilter) -> QueuePage[ClinicalQueueItem]:
        base = answers.alias("base_answer")
        source = (
            _within_context(base, base.c.qaset_id)
            .join(languages, languages.c.id == projects.c.base_language_id)
            .outerjoin(validations, validations.c.qaset_id == qasets.c.id)
        )
        state = _state(validations.c.current_state)
        conditions = [
            base.c.language_id == projects.c.base_language_id,
            *_conditions(queue_filter, state),
        ]
        rows, next_cursor, total = await self._page(
            select(
                qasets.c.id.label("key"),
                *_CONTEXT,
                languages.c.code.label("language_code"),
                base.c.text.label("answer_text"),
                state.label("state"),
            ).select_from(source),
            qasets.c.id,
            conditions,
            queue_filter,
        )
        variants = await self._base_variants([(r.key, r.base_language_id) for r in rows])
        items = tuple(
            ClinicalQueueItem(
                qaset_id=row.key,
                context=_context(row),
                base_language_code=row.language_code,
                answer_text=row.answer_text,
                variant_texts=tuple(variants[row.key]),
                state=row.state,
            )
            for row in rows
        )
        return QueuePage(items, next_cursor, total)

    async def translation(self, queue_filter: QueueFilter) -> QueuePage[TranslationQueueItem]:
        items = union_all(
            _items_with_state(answers, "answer", validations.c.answer_id),
            _items_with_state(question_variants, "variant", validations.c.variant_id),
        ).subquery("items")
        base = answers.alias("base_answer")
        source = (
            _within_context(items, items.c.qaset_id)
            .join(languages, languages.c.id == items.c.language_id)
            .outerjoin(
                base,
                and_(
                    base.c.qaset_id == qasets.c.id,
                    base.c.language_id == projects.c.base_language_id,
                ),
            )
        )
        state = _state(items.c.current_state)
        conditions = [
            items.c.language_id != projects.c.base_language_id,
            *_conditions(queue_filter, state),
        ]
        rows, next_cursor, total = await self._page(
            select(
                items.c.id.label("key"),
                items.c.kind,
                items.c.qaset_id,
                items.c.text,
                *_CONTEXT,
                languages.c.code.label("language_code"),
                base.c.text.label("base_answer_text"),
                state.label("state"),
            ).select_from(source),
            items.c.id,
            conditions,
            queue_filter,
        )
        base_of = {row.key: row.base_language_id for row in rows}
        sources: dict[UUID, list[SourceText]] = defaultdict(list)
        for kind, links, item_table, prefix in (
            ("answer", answer_translation_links, answers, "answer"),
            ("variant", variant_translation_links, question_variants, "variant"),
        ):
            ids = [row.key for row in rows if row.kind == kind]
            for item_id, source_id, text, language_id in await self._linked(
                links, item_table, prefix, ids
            ):
                if language_id == base_of[item_id]:
                    sources[item_id].append(SourceText(source_id, text))
        return QueuePage(
            tuple(
                TranslationQueueItem(
                    kind=row.kind,
                    item_id=row.key,
                    qaset_id=row.qaset_id,
                    context=_context(row),
                    language_code=row.language_code,
                    text=row.text,
                    sources=tuple(sources[row.key]),
                    fallback_base_answer_text=None if sources[row.key] else row.base_answer_text,
                    state=row.state,
                )
                for row in rows
            ),
            next_cursor,
            total,
        )

    async def audio(self, queue_filter: QueueFilter) -> QueuePage[AudioQueueItem]:
        qv = question_variants
        source = (
            _within_context(
                audios.outerjoin(answers, answers.c.id == audios.c.answer_id).outerjoin(
                    qv, qv.c.id == audios.c.variant_id
                ),
                func.coalesce(answers.c.qaset_id, qv.c.qaset_id),
            )
            .join(
                languages, languages.c.id == func.coalesce(answers.c.language_id, qv.c.language_id)
            )
            .outerjoin(validations, validations.c.audio_id == audios.c.id)
        )
        state = _state(validations.c.current_state)
        rows, next_cursor, total = await self._page(
            select(
                audios.c.id.label("key"),
                case((audios.c.answer_id.is_not(None), "answer"), else_="variant").label("kind"),
                func.coalesce(audios.c.answer_id, audios.c.variant_id).label("item_id"),
                qasets.c.id.label("qaset_id"),
                func.coalesce(answers.c.text, qv.c.text).label("text"),
                *_CONTEXT,
                languages.c.code.label("language_code"),
                state.label("state"),
            ).select_from(source),
            audios.c.id,
            _conditions(queue_filter, state),
            queue_filter,
        )
        return QueuePage(
            tuple(
                AudioQueueItem(
                    audio_id=row.key,
                    item_kind=row.kind,
                    item_id=row.item_id,
                    qaset_id=row.qaset_id,
                    context=_context(row),
                    language_code=row.language_code,
                    text=row.text,
                    state=row.state,
                )
                for row in rows
            ),
            next_cursor,
            total,
        )

    async def _page(
        self,
        query: Select[Any],
        key: ColumnElement[UUID],
        conditions: Sequence[ColumnElement[bool]],
        queue_filter: QueueFilter,
    ) -> tuple[Sequence[Any], UUID | None, int]:
        """One page after the cursor, ordered by ``key``, and the count of every match."""
        after = [] if queue_filter.cursor is None else [key > queue_filter.cursor]
        page = query.where(*conditions, *after).order_by(key).limit(queue_filter.limit + 1)
        rows = (await self._connection.execute(page)).all()
        counted = query.with_only_columns(func.count()).where(*conditions).order_by(None)
        total = int(await self._connection.scalar(counted) or 0)
        more = len(rows) > queue_filter.limit
        rows = rows[: queue_filter.limit]
        return rows, rows[-1].key if more else None, total

    async def _base_variants(self, pairs: list[tuple[UUID, UUID]]) -> dict[UUID, list[str]]:
        """The variants of each (QA set, base language), in creation order."""
        texts: dict[UUID, list[str]] = defaultdict(list)
        if not pairs:
            return texts
        qv = question_variants
        result = await self._connection.execute(
            select(qv.c.qaset_id, qv.c.text)
            .where(tuple_(qv.c.qaset_id, qv.c.language_id).in_(pairs))
            .order_by(qv.c.qaset_id, qv.c.created_at, qv.c.id)
        )
        for qaset_id, text in result:
            texts[qaset_id].append(text)
        return texts

    async def _linked(
        self, links: Table, items: Table, prefix: str, item_ids: list[UUID]
    ) -> list[tuple[UUID, UUID, str, UUID]]:
        """(item, linked item, its text, its language) for each link of ``item_ids``."""
        if not item_ids:
            return []
        low, high = links.c[f"{prefix}_low_id"], links.c[f"{prefix}_high_id"]

        def direction(mine: ColumnElement[UUID], other: ColumnElement[UUID]) -> Select[Any]:
            return (
                select(
                    mine.label("item_id"),
                    items.c.id,
                    items.c.text,
                    items.c.language_id,
                    links.c.created_at,
                    links.c.id.label("link_id"),
                )
                .select_from(links.join(items, items.c.id == other))
                .where(mine.in_(item_ids))
            )

        pairs = union_all(direction(low, high), direction(high, low)).subquery("pairs")
        result = await self._connection.execute(
            select(pairs.c.item_id, pairs.c.id, pairs.c.text, pairs.c.language_id).order_by(
                pairs.c.created_at, pairs.c.link_id
            )
        )
        return [(row[0], row[1], row[2], row[3]) for row in result]


def _items_with_state(table: Table, kind: str, subject: ColumnElement[Any]) -> Select[Any]:
    return select(
        literal(kind, Text).label("kind"),
        table.c.id,
        table.c.qaset_id,
        table.c.language_id,
        table.c.text,
        validations.c.current_state,
    ).select_from(table.outerjoin(validations, subject == table.c.id))
