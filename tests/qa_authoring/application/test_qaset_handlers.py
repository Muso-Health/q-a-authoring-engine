from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from qa_authoring.application.add_language_presence.command import AddLanguagePresenceCommand
from qa_authoring.application.add_language_presence.handler import AddLanguagePresenceHandler
from qa_authoring.application.add_question_variant.command import AddQuestionVariantCommand
from qa_authoring.application.add_question_variant.handler import AddQuestionVariantHandler
from qa_authoring.application.create_qaset.command import CreateQASetCommand
from qa_authoring.application.create_qaset.handler import CreateQASetHandler
from qa_authoring.application.delete_language.command import DeleteLanguageCommand
from qa_authoring.application.delete_language.handler import DeleteLanguageHandler
from qa_authoring.application.delete_qaset.command import DeleteQASetCommand
from qa_authoring.application.delete_qaset.handler import DeleteQASetHandler
from qa_authoring.application.delete_question_variant.command import (
    DeleteQuestionVariantCommand,
)
from qa_authoring.application.delete_question_variant.handler import (
    DeleteQuestionVariantHandler,
)
from qa_authoring.application.delete_theme.command import DeleteThemeCommand
from qa_authoring.application.delete_theme.handler import DeleteThemeHandler
from qa_authoring.application.get_qaset.command import GetQASetQuery
from qa_authoring.application.get_qaset.handler import GetQASetHandler
from qa_authoring.application.language_errors import LanguageInUseError
from qa_authoring.application.list_qasets.command import ListQASetsQuery
from qa_authoring.application.list_qasets.handler import ListQASetsHandler
from qa_authoring.application.qaset_errors import (
    AnswerAlreadyExistsError,
    QASetNotFoundError,
    UnknownLanguageError,
)
from qa_authoring.application.remove_language_presence.command import (
    RemoveLanguagePresenceCommand,
)
from qa_authoring.application.remove_language_presence.handler import (
    RemoveLanguagePresenceHandler,
)
from qa_authoring.application.theme_errors import ThemeHasQASetsError, ThemeNotFoundError
from qa_authoring.application.update_answer.command import UpdateAnswerCommand
from qa_authoring.application.update_answer.handler import UpdateAnswerHandler
from qa_authoring.application.update_question_variant.command import (
    UpdateQuestionVariantCommand,
)
from qa_authoring.application.update_question_variant.handler import (
    UpdateQuestionVariantHandler,
)
from qa_authoring.domain.model.language import Language
from qa_authoring.domain.model.project import Project
from qa_authoring.domain.model.protocol import Protocol
from qa_authoring.domain.model.qaset import (
    LanguageAlreadyPresentError,
    LanguageNotPresentError,
    LanguagePresenceRequiredError,
    QuestionVariantNotFoundError,
)
from qa_authoring.domain.model.theme import Theme
from qa_authoring.domain.value_objects.language_code import LanguageCode
from qa_authoring.domain.value_objects.naming import InvalidTextError
from tests.fakes import InMemoryStore, base_language, resetter, views

ACTOR = uuid4()


@pytest.fixture
def store() -> InMemoryStore:
    return InMemoryStore()


async def _language(store: InMemoryStore, code: str) -> UUID:
    language = Language.register(LanguageCode(code), code)
    await store.languages.add(language)
    return language.id


async def _theme(store: InMemoryStore, base_language_id: UUID | None = None) -> UUID:
    project = Project.create(name="P", base_language_id=base_language_id or uuid4())
    protocol = Protocol.create(project_id=project.id, name="Pr")
    theme = Theme.create(protocol_id=protocol.id, name="Fever")
    await store.projects.add(project)
    await store.protocols.add(protocol)
    await store.themes.add(theme)
    return theme.id


def _create(store: InMemoryStore) -> CreateQASetHandler:
    return CreateQASetHandler(store.qasets, store.themes, store.languages, base_language(store))


async def _qaset(store: InMemoryStore, theme_id: UUID, language_id: UUID) -> UUID:
    result = await _create(store)(
        CreateQASetCommand(theme_id=theme_id, language_id=language_id, answer_text="Rest.")
    )
    return result.id


async def _add_language(store: InMemoryStore, qaset_id: UUID, language_id: UUID) -> None:
    await AddLanguagePresenceHandler(store.qasets, store.languages)(
        AddLanguagePresenceCommand(qaset_id=qaset_id, language_id=language_id, answer_text="A")
    )


async def _add_variant(
    store: InMemoryStore, qaset_id: UUID, language_id: UUID, text: str = "Q?"
) -> UUID:
    result = await AddQuestionVariantHandler(store.qasets, resetter(store))(
        AddQuestionVariantCommand(
            qaset_id=qaset_id, language_id=language_id, text=text, actor_user_id=ACTOR
        )
    )
    return result.id


# --- create ---


async def test_create_qaset_with_its_first_answer(store: InMemoryStore) -> None:
    theme_id, fr = await _theme(store), await _language(store, "fr")

    result = await _create(store)(
        CreateQASetCommand(theme_id=theme_id, language_id=fr, answer_text=" Rest. ")
    )

    assert result.theme_id == theme_id
    [presence] = result.languages
    assert (presence.language_id, presence.answer.text, presence.variant_count) == (fr, "Rest.", 0)
    assert result.id in store.qasets.rows


async def test_create_qaset_refuses_an_answer_the_theme_already_has(store: InMemoryStore) -> None:
    fr, bm = await _language(store, "fr"), await _language(store, "bm")
    theme_id = await _theme(store, base_language_id=fr)
    existing = await _qaset(store, theme_id, fr)

    with pytest.raises(AnswerAlreadyExistsError) as raised:
        await _create(store)(
            CreateQASetCommand(theme_id=theme_id, language_id=fr, answer_text=" Rest. ")
        )
    assert raised.value.qaset_id == existing
    assert list(store.qasets.rows) == [existing]

    # A different answer, the same answer in another theme or outside the base language: created.
    other_theme = await _theme(store, base_language_id=fr)
    for theme, language, answer in (
        (theme_id, fr, "Drink."),
        (other_theme, fr, "Rest."),
        (theme_id, bm, "Rest."),
    ):
        await _create(store)(
            CreateQASetCommand(theme_id=theme, language_id=language, answer_text=answer)
        )
    assert len(store.qasets.rows) == 4


async def test_create_qaset_under_a_missing_theme(store: InMemoryStore) -> None:
    with pytest.raises(ThemeNotFoundError):
        await _qaset(store, uuid4(), await _language(store, "fr"))
    assert store.qasets.rows == {}


async def test_create_qaset_with_an_unknown_language(store: InMemoryStore) -> None:
    with pytest.raises(UnknownLanguageError):
        await _qaset(store, await _theme(store), uuid4())
    assert store.qasets.rows == {}


async def test_create_qaset_with_blank_answer(store: InMemoryStore) -> None:
    with pytest.raises(InvalidTextError):
        await _create(store)(
            CreateQASetCommand(
                theme_id=await _theme(store),
                language_id=await _language(store, "fr"),
                answer_text=" ",
            )
        )


# --- language presences ---


async def test_add_language_presence(store: InMemoryStore) -> None:
    fr, bm = await _language(store, "fr"), await _language(store, "bm")
    qaset_id = await _qaset(store, await _theme(store), fr)

    presence = await AddLanguagePresenceHandler(store.qasets, store.languages)(
        AddLanguagePresenceCommand(qaset_id=qaset_id, language_id=bm, answer_text=" Bambara ")
    )

    assert (presence.language_id, presence.answer.text, presence.variant_count) == (
        bm,
        "Bambara",
        0,
    )
    stored = store.qasets.rows[qaset_id]
    assert {p.language_id for p in stored.presences()} == {fr, bm}


async def test_add_duplicate_language_presence_is_a_conflict(store: InMemoryStore) -> None:
    fr = await _language(store, "fr")
    qaset_id = await _qaset(store, await _theme(store), fr)
    with pytest.raises(LanguageAlreadyPresentError):
        await _add_language(store, qaset_id, fr)


async def test_add_presence_validates_language_and_qaset(store: InMemoryStore) -> None:
    fr = await _language(store, "fr")
    qaset_id = await _qaset(store, await _theme(store), fr)
    with pytest.raises(UnknownLanguageError):
        await _add_language(store, qaset_id, uuid4())
    with pytest.raises(QASetNotFoundError):
        await _add_language(store, uuid4(), fr)


def _update(store: InMemoryStore) -> UpdateAnswerHandler:
    return UpdateAnswerHandler(
        store.qasets, store.themes, base_language(store), views(store), resetter(store)
    )


async def _rename(store: InMemoryStore, qaset_id: UUID, language_id: UUID, text: str) -> str:
    presence = await _update(store)(
        UpdateAnswerCommand(
            qaset_id=qaset_id, language_id=language_id, text=text, actor_user_id=ACTOR
        )
    )
    return presence.answer.text


async def test_an_answer_cannot_be_renamed_onto_another_sets_answer(store: InMemoryStore) -> None:
    fr, bm = await _language(store, "fr"), await _language(store, "bm")
    theme_id = await _theme(store, base_language_id=fr)
    rest = await _qaset(store, theme_id, fr)
    drink = (
        await _create(store)(
            CreateQASetCommand(theme_id=theme_id, language_id=fr, answer_text="Drink.")
        )
    ).id

    with pytest.raises(AnswerAlreadyExistsError) as raised:
        await _rename(store, drink, fr, " Rest. ")
    assert raised.value.qaset_id == rest
    assert store.qasets.rows[drink].presence(fr).answer.text == "Drink."

    assert await _rename(store, drink, fr, " Drink. ") == "Drink."
    assert await _rename(store, drink, fr, "Sleep.") == "Sleep."
    # Another theme's answers do not count, nor do answers outside the base language.
    elsewhere = await _qaset(store, await _theme(store, base_language_id=fr), fr)
    assert await _rename(store, elsewhere, fr, "Sleep.") == "Sleep."
    await _add_language(store, drink, bm)
    assert await _rename(store, drink, bm, "Rest.") == "Rest."


async def test_update_answer(store: InMemoryStore) -> None:
    fr = await _language(store, "fr")
    qaset_id = await _qaset(store, await _theme(store), fr)

    presence = await _update(store)(
        UpdateAnswerCommand(
            qaset_id=qaset_id, language_id=fr, text="Drink water.", actor_user_id=ACTOR
        )
    )

    assert presence.answer.text == "Drink water."
    assert store.qasets.rows[qaset_id].presence(fr).answer.text == "Drink water."
    with pytest.raises(LanguageNotPresentError):
        await _update(store)(
            UpdateAnswerCommand(
                qaset_id=qaset_id, language_id=uuid4(), text="x", actor_user_id=ACTOR
            )
        )


async def test_remove_language_presence_drops_its_variants(store: InMemoryStore) -> None:
    fr, bm = await _language(store, "fr"), await _language(store, "bm")
    qaset_id = await _qaset(store, await _theme(store), fr)
    await _add_language(store, qaset_id, bm)
    await _add_variant(store, qaset_id, bm)
    kept = await _add_variant(store, qaset_id, fr)

    await RemoveLanguagePresenceHandler(store.qasets, resetter(store))(
        RemoveLanguagePresenceCommand(qaset_id=qaset_id, language_id=bm, actor_user_id=ACTOR)
    )

    stored = store.qasets.rows[qaset_id]
    assert [p.language_id for p in stored.presences()] == [fr]
    assert [v.id for v in stored.variants] == [kept]
    with pytest.raises(LanguageNotPresentError):
        await RemoveLanguagePresenceHandler(store.qasets, resetter(store))(
            RemoveLanguagePresenceCommand(qaset_id=qaset_id, language_id=bm, actor_user_id=ACTOR)
        )


# --- variants ---


async def test_add_variant_to_an_absent_language_is_a_conflict(store: InMemoryStore) -> None:
    fr, bm = await _language(store, "fr"), await _language(store, "bm")
    qaset_id = await _qaset(store, await _theme(store), fr)
    with pytest.raises(LanguagePresenceRequiredError):
        await _add_variant(store, qaset_id, bm)
    assert store.qasets.rows[qaset_id].variants == ()


async def test_update_and_delete_variant(store: InMemoryStore) -> None:
    fr = await _language(store, "fr")
    qaset_id = await _qaset(store, await _theme(store), fr)
    variant_id = await _add_variant(store, qaset_id, fr, "What to do?")

    updated = await UpdateQuestionVariantHandler(store.qasets, views(store), resetter(store))(
        UpdateQuestionVariantCommand(
            qaset_id=qaset_id, variant_id=variant_id, text="Now what?", actor_user_id=ACTOR
        )
    )
    assert (updated.id, updated.language_id, updated.text) == (variant_id, fr, "Now what?")

    await DeleteQuestionVariantHandler(store.qasets, resetter(store))(
        DeleteQuestionVariantCommand(qaset_id=qaset_id, variant_id=variant_id, actor_user_id=ACTOR)
    )
    assert store.qasets.rows[qaset_id].variants == ()
    with pytest.raises(QuestionVariantNotFoundError):
        await DeleteQuestionVariantHandler(store.qasets, resetter(store))(
            DeleteQuestionVariantCommand(
                qaset_id=qaset_id, variant_id=variant_id, actor_user_id=ACTOR
            )
        )


# --- reads ---


async def test_get_groups_by_language_with_variant_counts(store: InMemoryStore) -> None:
    fr, bm = await _language(store, "fr"), await _language(store, "bm")
    qaset_id = await _qaset(store, await _theme(store), fr)
    await _add_language(store, qaset_id, bm)
    await _add_variant(store, qaset_id, fr, "One")
    await _add_variant(store, qaset_id, fr, "Two")
    await _add_variant(store, qaset_id, bm, "Three")

    result = await GetQASetHandler(store.qasets, views(store))(GetQASetQuery(qaset_id))

    by_language = {p.language_id: p for p in result.languages}
    assert {lang: p.variant_count for lang, p in by_language.items()} == {fr: 2, bm: 1}
    assert {v.text for v in by_language[fr].variants} == {"One", "Two"}
    assert all(v.language_id == fr for v in by_language[fr].variants)
    with pytest.raises(QASetNotFoundError):
        await GetQASetHandler(store.qasets, views(store))(GetQASetQuery(uuid4()))


async def test_list_by_theme_returns_only_its_qasets(store: InMemoryStore) -> None:
    fr, bm = await _language(store, "fr"), await _language(store, "bm")
    theme_a, theme_b = await _theme(store), await _theme(store)
    first = await _qaset(store, theme_a, fr)
    await _add_language(store, first, bm)
    await _add_variant(store, first, bm)
    second = await _qaset(store, theme_a, bm)
    await _qaset(store, theme_b, fr)

    results = await ListQASetsHandler(store.qasets, store.themes)(ListQASetsQuery(theme_a))

    summary = {r.id: {s.language_id: s.variant_count for s in r.languages} for r in results}
    assert summary == {first: {fr: 0, bm: 1}, second: {bm: 0}}
    with pytest.raises(ThemeNotFoundError):
        await ListQASetsHandler(store.qasets, store.themes)(ListQASetsQuery(uuid4()))


# --- deletes and guards ---


async def test_delete_qaset_removes_the_whole_aggregate(store: InMemoryStore) -> None:
    fr = await _language(store, "fr")
    qaset_id = await _qaset(store, await _theme(store), fr)
    await _add_variant(store, qaset_id, fr)

    await DeleteQASetHandler(store.qasets)(DeleteQASetCommand(qaset_id))

    assert qaset_id not in store.qasets.rows
    with pytest.raises(QASetNotFoundError):
        await DeleteQASetHandler(store.qasets)(DeleteQASetCommand(qaset_id))


async def test_delete_theme_with_qasets_is_a_conflict(store: InMemoryStore) -> None:
    theme_id = await _theme(store)
    await _qaset(store, theme_id, await _language(store, "fr"))
    with pytest.raises(ThemeHasQASetsError):
        await DeleteThemeHandler(store.themes, store.qasets)(DeleteThemeCommand(theme_id))
    assert theme_id in store.themes.rows


async def test_delete_language_used_by_a_qaset_is_a_conflict(store: InMemoryStore) -> None:
    fr, bm = await _language(store, "fr"), await _language(store, "bm")
    qaset_id = await _qaset(store, await _theme(store), fr)
    await _add_language(store, qaset_id, bm)
    with pytest.raises(LanguageInUseError):
        await DeleteLanguageHandler(store.languages, store.projects, store.qasets)(
            DeleteLanguageCommand(bm)
        )
    assert bm in store.languages.rows
