from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import pytest

from qa_authoring.application.archive_glossary_term.command import ArchiveGlossaryTermCommand
from qa_authoring.application.create_glossary_term.command import (
    CreateGlossaryTermCommand,
    GlossaryFormInput,
)
from qa_authoring.application.get_glossary_term.command import GetGlossaryTermQuery
from qa_authoring.application.glossary_errors import GlossaryTermNotFoundError
from qa_authoring.application.language_errors import LanguageNotFoundError
from qa_authoring.application.list_glossary_terms.command import ListGlossaryTermsQuery
from qa_authoring.application.patch import UNCHANGED
from qa_authoring.application.remove_glossary_form.command import RemoveGlossaryFormCommand
from qa_authoring.application.unarchive_glossary_term.command import (
    UnarchiveGlossaryTermCommand,
)
from qa_authoring.application.update_glossary_term.command import UpdateGlossaryTermCommand
from qa_authoring.application.upsert_glossary_form.command import UpsertGlossaryFormCommand
from qa_authoring.domain.model.glossary import (
    GlossaryFormNotFoundError,
    GlossaryStatus,
    InvalidGlossaryFieldError,
)
from qa_authoring.domain.model.language import Language
from qa_authoring.domain.value_objects.language_code import LanguageCode
from tests.fakes import NOW, in_memory_container

if TYPE_CHECKING:
    from uuid import UUID

    from config.container import Container
    from qa_authoring.application.glossary_response import GlossaryTermResult
    from tests.fakes import InMemoryStore


class World:
    def __init__(self) -> None:
        self.now = NOW
        self.container, self.store = in_memory_container(clock=lambda: self.now)
        self.fr = self._language("fr")
        self.bm = self._language("bm")

    def _language(self, code: str) -> UUID:
        language = Language.register(LanguageCode(code), code)
        self.store.languages.rows[language.id] = language
        return language.id

    async def run(self, build: str, command: Any) -> Any:
        container: Container = self.container
        return await container.run(getattr(container, build), command)

    async def create(self, label: str, *forms: GlossaryFormInput) -> GlossaryTermResult:
        result: GlossaryTermResult = await self.run(
            "build_create_glossary_term", CreateGlossaryTermCommand(label, forms=forms)
        )
        return result


@pytest.fixture
def world() -> World:
    return World()


async def test_create_with_initial_forms(world: World) -> None:
    result = await world.create(
        " malaria ",
        GlossaryFormInput(world.fr, "paludisme", synonyms=(" palu ", "palu", "")),
        GlossaryFormInput(world.bm, "sumaya"),
    )

    assert (result.label, result.note, result.status) == ("malaria", None, GlossaryStatus.ACTIVE)
    assert (result.created_at, result.updated_at) == (NOW, NOW)
    by_language = {f.language_id: f for f in result.forms}
    assert by_language[world.fr].synonyms == ("palu",)
    assert by_language[world.bm].preferred == "sumaya"
    store: InMemoryStore = world.store
    assert set(store.glossary.rows) == {result.id}


async def test_create_rejects_an_unknown_language_or_a_blank_field(world: World) -> None:
    unknown = uuid4()
    with pytest.raises(LanguageNotFoundError):
        await world.create("malaria", GlossaryFormInput(unknown, "x"))
    with pytest.raises(InvalidGlossaryFieldError) as raised:
        await world.create("malaria", GlossaryFormInput(world.fr, " "))
    assert raised.value.field == "preferred"
    with pytest.raises(InvalidGlossaryFieldError):
        await world.create(" ")
    assert world.store.glossary.rows == {}


async def test_update_label_and_note(world: World) -> None:
    term = await world.create("malaria")
    world.now = NOW + timedelta(hours=1)

    noted = await world.run(
        "build_update_glossary_term", UpdateGlossaryTermCommand(term.id, note="disease")
    )
    relabeled = await world.run(
        "build_update_glossary_term", UpdateGlossaryTermCommand(term.id, label="Malaria")
    )
    cleared = await world.run(
        "build_update_glossary_term", UpdateGlossaryTermCommand(term.id, note=None)
    )

    assert (noted.label, noted.note, noted.updated_at) == ("malaria", "disease", world.now)
    assert (relabeled.label, relabeled.note) == ("Malaria", "disease")
    assert (cleared.label, cleared.note) == ("Malaria", None)
    unchanged = UpdateGlossaryTermCommand(term.id, label=None, note=UNCHANGED)
    assert (await world.run("build_update_glossary_term", unchanged)).label == "Malaria"


async def test_archive_and_unarchive(world: World) -> None:
    term = await world.create("malaria")
    archived = await world.run("build_archive_glossary_term", ArchiveGlossaryTermCommand(term.id))
    assert archived.status is GlossaryStatus.ARCHIVED
    restored = await world.run(
        "build_unarchive_glossary_term", UnarchiveGlossaryTermCommand(term.id)
    )
    assert restored.status is GlossaryStatus.ACTIVE


async def test_upsert_replaces_the_languages_form(world: World) -> None:
    term = await world.create("malaria")
    command = UpsertGlossaryFormCommand(term.id, world.fr, "paludisme", synonyms=("palu",))

    first, created = await world.run("build_upsert_glossary_form", command)
    replaced = UpsertGlossaryFormCommand(term.id, world.fr, "malaria", avoid=("palu",), note="n")
    second, again = await world.run("build_upsert_glossary_form", replaced)

    assert (created, again) == (True, False)
    [form] = second.forms
    assert form.id == first.forms[0].id
    assert (form.preferred, form.synonyms, form.avoid, form.note) == (
        "malaria",
        (),
        ("palu",),
        "n",
    )
    assert len(world.store.glossary.rows[term.id].forms) == 1


async def test_upsert_checks_the_term_and_the_language(world: World) -> None:
    term = await world.create("malaria")
    with pytest.raises(GlossaryTermNotFoundError):
        await world.run(
            "build_upsert_glossary_form", UpsertGlossaryFormCommand(uuid4(), world.fr, "x")
        )
    with pytest.raises(LanguageNotFoundError):
        await world.run(
            "build_upsert_glossary_form", UpsertGlossaryFormCommand(term.id, uuid4(), "x")
        )
    assert world.store.glossary.rows[term.id].forms == ()


async def test_remove_a_form(world: World) -> None:
    term = await world.create("malaria", GlossaryFormInput(world.fr, "paludisme"))
    await world.run("build_remove_glossary_form", RemoveGlossaryFormCommand(term.id, world.fr))
    assert world.store.glossary.rows[term.id].forms == ()
    with pytest.raises(GlossaryFormNotFoundError):
        await world.run("build_remove_glossary_form", RemoveGlossaryFormCommand(term.id, world.fr))


@pytest.mark.parametrize(
    ("build", "command"),
    [
        ("build_get_glossary_term", GetGlossaryTermQuery(uuid4())),
        ("build_update_glossary_term", UpdateGlossaryTermCommand(uuid4(), label="x")),
        ("build_archive_glossary_term", ArchiveGlossaryTermCommand(uuid4())),
        ("build_unarchive_glossary_term", UnarchiveGlossaryTermCommand(uuid4())),
        ("build_remove_glossary_form", RemoveGlossaryFormCommand(uuid4(), uuid4())),
    ],
)
async def test_an_unknown_term(world: World, build: str, command: Any) -> None:
    with pytest.raises(GlossaryTermNotFoundError):
        await world.run(build, command)


async def test_list_filters_by_status_searches_and_pages(world: World) -> None:
    malaria = await world.create("Malaria", GlossaryFormInput(world.fr, "paludisme"))
    fever = await world.create("fever", GlossaryFormInput(world.fr, "fièvre", synonyms=("palu",)))
    cough = await world.create("cough")
    await world.run("build_archive_glossary_term", ArchiveGlossaryTermCommand(cough.id))

    async def labels(**kwargs: Any) -> tuple[list[str], int]:
        page = await world.run("build_list_glossary_terms", ListGlossaryTermsQuery(**kwargs))
        return [t.label for t in page.items], page.total

    assert await labels() == (["fever", "Malaria"], 2)
    assert await labels(status=GlossaryStatus.ARCHIVED) == (["cough"], 1)
    assert await labels(status=None) == (["cough", "fever", "Malaria"], 3)
    assert await labels(search="PALU") == (["fever", "Malaria"], 2)
    assert await labels(search="fievre") == (["fever"], 1)
    assert await labels(search="  ") == (["fever", "Malaria"], 2)
    assert await labels(status=None, limit=2) == (["cough", "fever"], 3)
    assert await labels(status=None, limit=2, offset=2) == (["Malaria"], 3)
    assert {malaria.id, fever.id} == {
        t.id for t in (await world.run("build_list_glossary_terms", ListGlossaryTermsQuery())).items
    }
