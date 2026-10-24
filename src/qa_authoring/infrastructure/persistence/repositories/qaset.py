from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any

from sqlalchemy import Table, delete, exists, insert, select, tuple_, update
from sqlalchemy.exc import IntegrityError

from qa_authoring.application.qaset_errors import UnknownLanguageError
from qa_authoring.application.theme_errors import ThemeNotFoundError
from qa_authoring.domain.model.qaset import (
    Answer,
    AudioReference,
    QASet,
    QuestionVariant,
    TranslationLink,
)
from qa_authoring.infrastructure.persistence.repositories._integrity import (
    FOREIGN_KEY_VIOLATION,
    constraint_name,
    sqlstate,
)
from qa_authoring.infrastructure.persistence.schema.qaset import (
    answer_translation_links,
    answers,
    audios,
    qaset_categories,
    qasets,
    question_variants,
    variant_intents,
    variant_translation_links,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncConnection


def _audio(row: Any) -> AudioReference:
    return AudioReference(
        id=row.id,
        storage_uri=row.storage_uri,
        mime_type=row.mime_type,
        duration_ms=row.duration_ms,
        checksum_sha256=row.checksum_sha256,
        size_bytes=row.size_bytes,
        created_at=row.created_at,
    )


class _LinkTable:
    """One translation-link table: ``<item>_low_id`` / ``<item>_high_id`` columns."""

    def __init__(self, table: Table, item: str) -> None:
        self.table = table
        self.low = table.c[f"{item}_low_id"]
        self.high = table.c[f"{item}_high_id"]

    def row(self, qaset_id: UUID, link: TranslationLink) -> dict[str, UUID]:
        return {
            "id": link.id,
            "qaset_id": qaset_id,
            self.low.key: link.low_id,
            self.high.key: link.high_id,
        }


_ANSWER_LINKS = _LinkTable(answer_translation_links, "answer")
_VARIANT_LINKS = _LinkTable(variant_translation_links, "variant")


class PostgresQASetRepository:
    """Persists the QASet aggregate across ``qasets``, ``answers`` and ``question_variants``.

    ``save`` diffs the aggregate against the stored child rows (delete removed, insert new, update
    changed text), so surviving rows keep their ``created_at``. Children and translation links load
    in creation order (``created_at`` then ``id``), which is the order the aggregate keeps them in.
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
        await self._save_intents(qaset)
        await self._save_categories(qaset)
        await self._save_audios(qaset)
        await self._save_links(_ANSWER_LINKS, qaset.id, qaset.answer_links)
        await self._save_links(_VARIANT_LINKS, qaset.id, qaset.variant_links)

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
        # Links and attachments last: they reference answers/variants inserted above. Those of
        # removed items are already gone (ON DELETE CASCADE).
        await self._save_intents(qaset)
        await self._save_categories(qaset)
        await self._save_audios(qaset)
        await self._save_links(_ANSWER_LINKS, qaset.id, qaset.answer_links)
        await self._save_links(_VARIANT_LINKS, qaset.id, qaset.variant_links)

    async def delete(self, qaset_id: UUID) -> None:
        await self._connection.execute(delete(qasets).where(qasets.c.id == qaset_id))

    async def exists_for_theme(self, theme_id: UUID) -> bool:
        query = select(exists().where(qasets.c.theme_id == theme_id))
        return bool(await self._connection.scalar(query))

    async def uses_language(self, language_id: UUID) -> bool:
        # Every variant's language has an answer (composite FK), so answers are enough.
        query = select(exists().where(answers.c.language_id == language_id))
        return bool(await self._connection.scalar(query))

    async def uses_intent(self, intent_id: UUID) -> bool:
        query = select(exists().where(variant_intents.c.intent_id == intent_id))
        return bool(await self._connection.scalar(query))

    async def find_audio(self, audio_id: UUID) -> AudioReference | None:
        row = (
            await self._connection.execute(select(audios).where(audios.c.id == audio_id))
        ).one_or_none()
        return None if row is None else _audio(row)

    async def storage_uri_in_use(self, storage_uri: str) -> bool:
        query = select(exists().where(audios.c.storage_uri == storage_uri))
        return bool(await self._connection.scalar(query))

    async def _save_audios(self, qaset: QASet) -> None:
        # Audio references are immutable: a replacement is a new row, so a diff of ids suffices.
        answer_ids = [a.id for a in qaset.answers]
        variant_ids = [v.id for v in qaset.variants]
        stored: set[UUID] = set(
            await self._connection.scalars(
                select(audios.c.id).where(
                    audios.c.answer_id.in_(answer_ids) | audios.c.variant_id.in_(variant_ids)
                )
            )
        )
        current: list[tuple[str, UUID, AudioReference]] = [
            *(("answer_id", a.id, a.audio) for a in qaset.answers if a.audio is not None),
            *(("variant_id", v.id, v.audio) for v in qaset.variants if v.audio is not None),
        ]
        missing = stored - {audio.id for _, _, audio in current}
        if missing:
            await self._connection.execute(delete(audios).where(audios.c.id.in_(missing)))
        new = [
            {
                "id": audio.id,
                column: item_id,
                "storage_uri": audio.storage_uri,
                "mime_type": audio.mime_type,
                "duration_ms": audio.duration_ms,
                "checksum_sha256": audio.checksum_sha256,
                "size_bytes": audio.size_bytes,
                "created_at": audio.created_at,
            }
            for column, item_id, audio in current
            if audio.id not in stored
        ]
        for row in new:
            await self._connection.execute(insert(audios).values(**row))

    async def uses_category(self, category_id: UUID) -> bool:
        query = select(exists().where(qaset_categories.c.category_id == category_id))
        return bool(await self._connection.scalar(query))

    async def _save_categories(self, qaset: QASet) -> None:
        stored: set[UUID] = set(
            await self._connection.scalars(
                select(qaset_categories.c.category_id).where(
                    qaset_categories.c.qaset_id == qaset.id
                )
            )
        )
        missing = stored - set(qaset.category_ids)
        if missing:
            await self._connection.execute(
                delete(qaset_categories).where(
                    qaset_categories.c.qaset_id == qaset.id,
                    qaset_categories.c.category_id.in_(missing),
                )
            )
        new = [
            {"qaset_id": qaset.id, "category_id": c} for c in qaset.category_ids if c not in stored
        ]
        if new:
            await self._connection.execute(insert(qaset_categories), new)

    async def _save_intents(self, qaset: QASet) -> None:
        stored = {
            (row.variant_id, row.intent_id)
            for row in await self._connection.execute(
                select(variant_intents.c.variant_id, variant_intents.c.intent_id)
                .join(question_variants, question_variants.c.id == variant_intents.c.variant_id)
                .where(question_variants.c.qaset_id == qaset.id)
            )
        }
        current = {(v.id, i) for v in qaset.variants for i in v.intent_ids}
        missing = stored - current
        if missing:
            await self._connection.execute(
                delete(variant_intents).where(
                    tuple_(variant_intents.c.variant_id, variant_intents.c.intent_id).in_(missing)
                )
            )
        # In each variant's attachment order, so created_at follows it.
        new = [
            {"variant_id": v.id, "intent_id": i}
            for v in qaset.variants
            for i in v.intent_ids
            if (v.id, i) not in stored
        ]
        if new:
            await self._connection.execute(insert(variant_intents), new)

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

    async def _save_links(
        self, links: _LinkTable, qaset_id: UUID, current: Sequence[TranslationLink]
    ) -> None:
        stored: set[UUID] = set(
            await self._connection.scalars(
                select(links.table.c.id).where(links.table.c.qaset_id == qaset_id)
            )
        )
        missing = stored - {link.id for link in current}
        if missing:
            await self._connection.execute(delete(links.table).where(links.table.c.id.in_(missing)))
        new = [links.row(qaset_id, link) for link in current if link.id not in stored]
        if new:
            await self._connection.execute(insert(links.table), new)

    async def _load_links(
        self, links: _LinkTable, qaset_ids: list[UUID]
    ) -> defaultdict[UUID, list[TranslationLink]]:
        by_qaset: defaultdict[UUID, list[TranslationLink]] = defaultdict(list)
        rows = await self._connection.execute(
            select(links.table.c.id, links.table.c.qaset_id, links.low, links.high)
            .where(links.table.c.qaset_id.in_(qaset_ids))
            .order_by(links.table.c.created_at, links.table.c.id)
        )
        for row in rows:
            by_qaset[row.qaset_id].append(TranslationLink(row.id, row[2], row[3]))
        return by_qaset

    async def _hydrate(self, rows: Sequence[Any]) -> tuple[QASet, ...]:
        if not rows:
            return ()
        ids = [row.id for row in rows]
        audio_by_item: dict[UUID, AudioReference] = {}
        for row in await self._connection.execute(
            select(audios)
            .outerjoin(answers, answers.c.id == audios.c.answer_id)
            .outerjoin(question_variants, question_variants.c.id == audios.c.variant_id)
            .where(answers.c.qaset_id.in_(ids) | question_variants.c.qaset_id.in_(ids))
        ):
            audio_by_item[row.answer_id or row.variant_id] = _audio(row)
        answers_by_qaset: defaultdict[UUID, list[Answer]] = defaultdict(list)
        for a in await self._connection.execute(
            select(answers)
            .where(answers.c.qaset_id.in_(ids))
            .order_by(answers.c.created_at, answers.c.id)
        ):
            answers_by_qaset[a.qaset_id].append(
                Answer(a.id, a.language_id, a.text, audio_by_item.get(a.id))
            )
        intents_by_variant: defaultdict[UUID, list[UUID]] = defaultdict(list)
        for row in await self._connection.execute(
            select(variant_intents.c.variant_id, variant_intents.c.intent_id)
            .join(question_variants, question_variants.c.id == variant_intents.c.variant_id)
            .where(question_variants.c.qaset_id.in_(ids))
            .order_by(variant_intents.c.created_at, variant_intents.c.intent_id)
        ):
            intents_by_variant[row.variant_id].append(row.intent_id)
        variants_by_qaset: defaultdict[UUID, list[QuestionVariant]] = defaultdict(list)
        for v in await self._connection.execute(
            select(question_variants)
            .where(question_variants.c.qaset_id.in_(ids))
            .order_by(question_variants.c.created_at, question_variants.c.id)
        ):
            variants_by_qaset[v.qaset_id].append(
                QuestionVariant(
                    v.id,
                    v.language_id,
                    v.text,
                    intents_by_variant[v.id],
                    audio_by_item.get(v.id),
                )
            )
        categories_by_qaset: defaultdict[UUID, list[UUID]] = defaultdict(list)
        for row in await self._connection.execute(
            select(qaset_categories.c.qaset_id, qaset_categories.c.category_id)
            .where(qaset_categories.c.qaset_id.in_(ids))
            .order_by(qaset_categories.c.created_at, qaset_categories.c.category_id)
        ):
            categories_by_qaset[row.qaset_id].append(row.category_id)
        answer_links = await self._load_links(_ANSWER_LINKS, ids)
        variant_links = await self._load_links(_VARIANT_LINKS, ids)
        return tuple(
            QASet(
                row.id,
                row.theme_id,
                answers=answers_by_qaset[row.id],
                variants=variants_by_qaset[row.id],
                answer_links=answer_links[row.id],
                variant_links=variant_links[row.id],
                category_ids=categories_by_qaset[row.id],
            )
            for row in rows
        )
