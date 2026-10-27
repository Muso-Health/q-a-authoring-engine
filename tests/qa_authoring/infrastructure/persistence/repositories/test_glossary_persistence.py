from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from qa_authoring.application.language_errors import LanguageInUseError
from qa_authoring.application.qaset_errors import UnknownLanguageError
from qa_authoring.domain.model.glossary import GlossaryStatus, GlossaryTerm
from qa_authoring.domain.model.language import Language
from qa_authoring.domain.value_objects.language_code import LanguageCode
from qa_authoring.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncEngine

pytestmark = pytest.mark.integration

T0 = datetime(2026, 10, 27, 9, tzinfo=UTC)
T1 = T0 + timedelta(hours=1)


async def _languages(engine: AsyncEngine) -> tuple[UUID, UUID]:
    fr = Language.register(LanguageCode("fr"), "French")
    bm = Language.register(LanguageCode("bm"), "Bambara")
    async with SqlAlchemyUnitOfWork(engine) as uow:
        await uow.languages.add(fr)
        await uow.languages.add(bm)
    return fr.id, bm.id


async def _add(engine: AsyncEngine, term: GlossaryTerm) -> None:
    async with SqlAlchemyUnitOfWork(engine) as uow:
        await uow.glossary.add(term)


async def _get(engine: AsyncEngine, term_id: UUID) -> GlossaryTerm | None:
    async with SqlAlchemyUnitOfWork(engine) as uow:
        return await uow.glossary.get(term_id)


async def test_a_term_round_trips_with_its_forms(migrated_engine: AsyncEngine) -> None:
    fr, bm = await _languages(migrated_engine)
    term = GlossaryTerm.create("malaria", note="the disease", at=T0)
    term.put_form(fr, "paludisme", synonyms=["palu", "fièvre des marais"], avoid=["malaria"], at=T0)
    term.put_form(bm, "sumaya", note="spoken", at=T0)
    await _add(migrated_engine, term)

    stored = await _get(migrated_engine, term.id)

    assert stored is not None
    assert (stored.label, stored.note, stored.status) == ("malaria", "the disease", term.status)
    assert (stored.created_at, stored.updated_at) == (T0, T0)
    assert [
        (f.id, f.language_id, f.preferred, f.synonyms, f.avoid, f.note) for f in stored.forms
    ] == [(f.id, f.language_id, f.preferred, f.synonyms, f.avoid, f.note) for f in term.forms]
    assert await _get(migrated_engine, uuid4()) is None


async def test_save_replaces_updates_and_removes_forms(migrated_engine: AsyncEngine) -> None:
    fr, bm = await _languages(migrated_engine)
    term = GlossaryTerm.create("malaria", at=T0)
    form, _ = term.put_form(fr, "paludisme", at=T0)
    term.put_form(bm, "sumaya", at=T0)
    await _add(migrated_engine, term)

    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        locked = await uow.glossary.get_for_update(term.id)
        assert locked is not None
        locked.relabel("Malaria", at=T1)
        locked.archive(at=T1)
        locked.put_form(fr, "malaria", synonyms=["palu"], at=T1)
        locked.remove_form(bm, at=T1)
        await uow.glossary.save(locked)

    stored = await _get(migrated_engine, term.id)
    assert stored is not None
    assert (stored.label, stored.status, stored.updated_at) == (
        "Malaria",
        GlossaryStatus.ARCHIVED,
        T1,
    )
    [kept] = stored.forms
    assert (kept.id, kept.preferred, kept.synonyms) == (form.id, "malaria", ("palu",))


async def test_one_form_per_term_and_language(migrated_engine: AsyncEngine) -> None:
    fr, _ = await _languages(migrated_engine)
    term = GlossaryTerm.create("malaria", at=T0)
    term.put_form(fr, "paludisme", at=T0)
    await _add(migrated_engine, term)

    with pytest.raises(IntegrityError, match="uq_glossary_forms_term_id_language_id"):
        async with migrated_engine.begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO glossary_forms (id, term_id, language_id, preferred) "
                    "VALUES (:id, :term, :language, 'palu')"
                ),
                {"id": uuid4(), "term": term.id, "language": fr},
            )


async def test_forms_need_a_known_language_and_keep_it_in_use(
    migrated_engine: AsyncEngine,
) -> None:
    fr, _ = await _languages(migrated_engine)
    orphan = GlossaryTerm.create("fever", at=T0)
    orphan.put_form(uuid4(), "fièvre", at=T0)
    with pytest.raises(UnknownLanguageError):
        await _add(migrated_engine, orphan)
    assert await _get(migrated_engine, orphan.id) is None

    term = GlossaryTerm.create("malaria", at=T0)
    term.put_form(fr, "paludisme", at=T0)
    await _add(migrated_engine, term)
    with pytest.raises(LanguageInUseError):
        async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
            await uow.languages.delete(fr)


async def test_list_filters_searches_and_pages(migrated_engine: AsyncEngine) -> None:
    fr, _ = await _languages(migrated_engine)
    malaria = GlossaryTerm.create("Malaria", at=T0)
    malaria.put_form(fr, "Paludisme", avoid=["palu_100%"], at=T0)
    fever = GlossaryTerm.create("fever", at=T0)
    fever.put_form(fr, "fièvre", synonyms=["température"], at=T0)
    cough = GlossaryTerm.create("cough", at=T0)
    cough.archive(at=T0)
    for term in (malaria, fever, cough):
        await _add(migrated_engine, term)

    async def labels(
        status: GlossaryStatus | None = GlossaryStatus.ACTIVE,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[str], int]:
        async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
            terms, total = await uow.glossary.list(
                status=status, search=search, limit=limit, offset=offset
            )
        return [t.label for t in terms], total

    assert await labels() == (["fever", "Malaria"], 2)
    assert await labels(GlossaryStatus.ARCHIVED) == (["cough"], 1)
    assert await labels(None) == (["cough", "fever", "Malaria"], 3)
    assert await labels(search="FIEVRE") == (["fever"], 1)
    assert await labels(search="ludis") == (["Malaria"], 1)
    assert await labels(search="temperature") == (["fever"], 1)
    assert await labels(search="_100%") == (["Malaria"], 1)
    assert await labels(search="%") == (["Malaria"], 1)
    assert await labels(search="cough") == ([], 0)
    assert await labels(None, limit=2) == (["cough", "fever"], 3)
    assert await labels(None, limit=2, offset=2) == (["Malaria"], 3)
    # The forms of a listed term come along.
    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        terms, _ = await uow.glossary.list(
            status=GlossaryStatus.ACTIVE, search="fever", limit=50, offset=0
        )
    assert [f.preferred for f in terms[0].forms] == ["fièvre"]


async def test_a_large_term_is_stored_and_found(migrated_engine: AsyncEngine) -> None:
    fr, _ = await _languages(migrated_engine)
    term = GlossaryTerm.create("dosage", at=T0)
    synonyms = [f"posologie numéro {n:04d} du traitement" for n in range(300)]
    term.put_form(fr, "posologie", synonyms=synonyms, at=T0)
    await _add(migrated_engine, term)

    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        terms, total = await uow.glossary.list(
            status=GlossaryStatus.ACTIVE, search="NUMERO 0299", limit=50, offset=0
        )
    assert (total, [t.id for t in terms]) == (1, [term.id])
    assert len(terms[0].search_text) > 6000
