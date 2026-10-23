from __future__ import annotations

from uuid import uuid4

import pytest

from qa_authoring.application.delete_language.command import DeleteLanguageCommand
from qa_authoring.application.delete_language.handler import DeleteLanguageHandler
from qa_authoring.application.get_language.command import GetLanguageQuery
from qa_authoring.application.get_language.handler import GetLanguageHandler
from qa_authoring.application.language_errors import (
    LanguageCodeAlreadyExistsError,
    LanguageNotFoundError,
)
from qa_authoring.application.list_languages.command import ListLanguagesQuery
from qa_authoring.application.list_languages.handler import ListLanguagesHandler
from qa_authoring.application.register_language.command import RegisterLanguageCommand
from qa_authoring.application.register_language.handler import RegisterLanguageHandler
from qa_authoring.application.update_language.command import UpdateLanguageCommand
from qa_authoring.application.update_language.handler import UpdateLanguageHandler
from qa_authoring.domain.model.language import InvalidLanguageNameError
from qa_authoring.domain.value_objects.language_code import InvalidLanguageCodeError, LanguageCode
from tests.fakes import (
    InMemoryLanguageRepository,
    InMemoryProjectRepository,
    InMemoryQASetRepository,
)


@pytest.fixture
def repo() -> InMemoryLanguageRepository:
    return InMemoryLanguageRepository()


async def _register(repo: InMemoryLanguageRepository, code: str, name: str) -> object:
    return await RegisterLanguageHandler(repo)(RegisterLanguageCommand(code=code, name=name))


async def test_register_stores_and_returns_the_language(repo: InMemoryLanguageRepository) -> None:
    result = await RegisterLanguageHandler(repo)(
        RegisterLanguageCommand(code="bm_fr", name=" Bambara (French) ")
    )

    assert result.code == "bm_fr"
    assert result.name == "Bambara (French)"
    stored = await repo.get(result.id)
    assert stored is not None
    assert stored.code == LanguageCode("bm_fr")


async def test_register_rejects_a_duplicate_code(repo: InMemoryLanguageRepository) -> None:
    await _register(repo, "fr", "French")
    with pytest.raises(LanguageCodeAlreadyExistsError):
        await _register(repo, "fr", "Français")
    assert len(repo.rows) == 1


async def test_register_rejects_an_invalid_code(repo: InMemoryLanguageRepository) -> None:
    with pytest.raises(InvalidLanguageCodeError):
        await _register(repo, "fr-FR", "French")
    assert repo.rows == {}


async def test_register_rejects_a_blank_name(repo: InMemoryLanguageRepository) -> None:
    with pytest.raises(InvalidLanguageNameError):
        await _register(repo, "fr", "  ")


async def test_list_returns_registered_languages_ordered_by_code(
    repo: InMemoryLanguageRepository,
) -> None:
    await _register(repo, "fr", "French")
    await _register(repo, "bm", "Bambara")

    results = await ListLanguagesHandler(repo)(ListLanguagesQuery())

    assert [(r.code, r.name) for r in results] == [("bm", "Bambara"), ("fr", "French")]


async def test_list_is_empty_when_nothing_is_registered(repo: InMemoryLanguageRepository) -> None:
    assert await ListLanguagesHandler(repo)(ListLanguagesQuery()) == ()


async def test_get_returns_the_language(repo: InMemoryLanguageRepository) -> None:
    created = await RegisterLanguageHandler(repo)(
        RegisterLanguageCommand(code="en", name="English")
    )
    assert await GetLanguageHandler(repo)(GetLanguageQuery(language_id=created.id)) == created


async def test_get_missing_id_raises_not_found(repo: InMemoryLanguageRepository) -> None:
    with pytest.raises(LanguageNotFoundError):
        await GetLanguageHandler(repo)(GetLanguageQuery(language_id=uuid4()))


async def test_update_renames_and_keeps_the_code(repo: InMemoryLanguageRepository) -> None:
    created = await RegisterLanguageHandler(repo)(RegisterLanguageCommand(code="fr", name="French"))

    updated = await UpdateLanguageHandler(repo)(
        UpdateLanguageCommand(language_id=created.id, name="Français")
    )

    assert updated.id == created.id
    assert updated.code == "fr"
    assert updated.name == "Français"
    stored = await repo.get(created.id)
    assert stored is not None
    assert stored.name == "Français"


async def test_update_missing_id_raises_not_found(repo: InMemoryLanguageRepository) -> None:
    with pytest.raises(LanguageNotFoundError):
        await UpdateLanguageHandler(repo)(UpdateLanguageCommand(language_id=uuid4(), name="X"))


async def test_delete_removes_the_language(repo: InMemoryLanguageRepository) -> None:
    created = await RegisterLanguageHandler(repo)(RegisterLanguageCommand(code="fr", name="French"))

    await DeleteLanguageHandler(repo, InMemoryProjectRepository(), InMemoryQASetRepository())(
        DeleteLanguageCommand(language_id=created.id)
    )

    assert await repo.get(created.id) is None


async def test_delete_missing_id_raises_not_found(repo: InMemoryLanguageRepository) -> None:
    with pytest.raises(LanguageNotFoundError):
        await DeleteLanguageHandler(repo, InMemoryProjectRepository(), InMemoryQASetRepository())(
            DeleteLanguageCommand(language_id=uuid4())
        )


async def test_a_deleted_code_can_be_registered_again(repo: InMemoryLanguageRepository) -> None:
    created = await RegisterLanguageHandler(repo)(RegisterLanguageCommand(code="fr", name="French"))
    await DeleteLanguageHandler(repo, InMemoryProjectRepository(), InMemoryQASetRepository())(
        DeleteLanguageCommand(language_id=created.id)
    )

    again = await RegisterLanguageHandler(repo)(RegisterLanguageCommand(code="fr", name="French"))

    assert again.id != created.id
