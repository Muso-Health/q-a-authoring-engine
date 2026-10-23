from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from qa_authoring.application.create_project.command import CreateProjectCommand
from qa_authoring.application.create_project.handler import CreateProjectHandler
from qa_authoring.application.create_protocol.command import CreateProtocolCommand
from qa_authoring.application.create_protocol.handler import CreateProtocolHandler
from qa_authoring.application.create_theme.command import CreateThemeCommand
from qa_authoring.application.create_theme.handler import CreateThemeHandler
from qa_authoring.application.delete_language.command import DeleteLanguageCommand
from qa_authoring.application.delete_language.handler import DeleteLanguageHandler
from qa_authoring.application.delete_project.command import DeleteProjectCommand
from qa_authoring.application.delete_project.handler import DeleteProjectHandler
from qa_authoring.application.delete_protocol.command import DeleteProtocolCommand
from qa_authoring.application.delete_protocol.handler import DeleteProtocolHandler
from qa_authoring.application.delete_theme.command import DeleteThemeCommand
from qa_authoring.application.delete_theme.handler import DeleteThemeHandler
from qa_authoring.application.get_project.command import GetProjectQuery
from qa_authoring.application.get_project.handler import GetProjectHandler
from qa_authoring.application.get_protocol.command import GetProtocolQuery
from qa_authoring.application.get_protocol.handler import GetProtocolHandler
from qa_authoring.application.get_theme.command import GetThemeQuery
from qa_authoring.application.get_theme.handler import GetThemeHandler
from qa_authoring.application.language_errors import LanguageInUseError
from qa_authoring.application.list_projects.command import ListProjectsQuery
from qa_authoring.application.list_projects.handler import ListProjectsHandler
from qa_authoring.application.list_protocols.command import ListProtocolsQuery
from qa_authoring.application.list_protocols.handler import ListProtocolsHandler
from qa_authoring.application.list_themes.command import ListThemesQuery
from qa_authoring.application.list_themes.handler import ListThemesHandler
from qa_authoring.application.patch import UNCHANGED
from qa_authoring.application.project_errors import (
    ProjectHasProtocolsError,
    ProjectNotFoundError,
    UnknownBaseLanguageError,
)
from qa_authoring.application.protocol_errors import (
    ProtocolHasThemesError,
    ProtocolNotFoundError,
)
from qa_authoring.application.register_language.command import RegisterLanguageCommand
from qa_authoring.application.register_language.handler import RegisterLanguageHandler
from qa_authoring.application.theme_errors import ThemeNotFoundError
from qa_authoring.application.update_project.command import UpdateProjectCommand
from qa_authoring.application.update_project.handler import UpdateProjectHandler
from qa_authoring.application.update_protocol.command import UpdateProtocolCommand
from qa_authoring.application.update_protocol.handler import UpdateProtocolHandler
from qa_authoring.application.update_theme.command import UpdateThemeCommand
from qa_authoring.application.update_theme.handler import UpdateThemeHandler
from qa_authoring.domain.value_objects.naming import InvalidNameError
from tests.fakes import InMemoryStore


@pytest.fixture
def store() -> InMemoryStore:
    return InMemoryStore()


async def _language(store: InMemoryStore, code: str = "fr") -> UUID:
    result = await RegisterLanguageHandler(store.languages)(
        RegisterLanguageCommand(code=code, name=code)
    )
    return result.id


async def _project(store: InMemoryStore, name: str = "Malaria") -> UUID:
    language_id = await _language(store, f"l{len(store.languages.rows) * 'x'}")
    result = await CreateProjectHandler(store.projects, store.languages)(
        CreateProjectCommand(name=name, description=None, base_language_id=language_id)
    )
    return result.id


async def _protocol(store: InMemoryStore, project_id: UUID, name: str = "Triage") -> UUID:
    result = await CreateProtocolHandler(store.protocols, store.projects)(
        CreateProtocolCommand(project_id=project_id, name=name, description=None)
    )
    return result.id


async def _theme(store: InMemoryStore, protocol_id: UUID, name: str = "Fever") -> UUID:
    result = await CreateThemeHandler(store.themes, store.protocols)(
        CreateThemeCommand(protocol_id=protocol_id, name=name, description=None)
    )
    return result.id


# --- Project ---


async def test_create_project_with_an_existing_base_language(store: InMemoryStore) -> None:
    language_id = await _language(store)

    result = await CreateProjectHandler(store.projects, store.languages)(
        CreateProjectCommand(name=" Malaria ", description=" CHW ", base_language_id=language_id)
    )

    assert (result.name, result.description, result.base_language_id) == (
        "Malaria",
        "CHW",
        language_id,
    )
    assert result.id in store.projects.rows


async def test_create_project_rejects_an_unknown_base_language(store: InMemoryStore) -> None:
    with pytest.raises(UnknownBaseLanguageError):
        await CreateProjectHandler(store.projects, store.languages)(
            CreateProjectCommand(name="Malaria", description=None, base_language_id=uuid4())
        )
    assert store.projects.rows == {}


async def test_create_project_rejects_a_blank_name(store: InMemoryStore) -> None:
    language_id = await _language(store)
    with pytest.raises(InvalidNameError):
        await CreateProjectHandler(store.projects, store.languages)(
            CreateProjectCommand(name=" ", description=None, base_language_id=language_id)
        )


async def test_list_projects_is_ordered_by_name(store: InMemoryStore) -> None:
    await _project(store, "Tuberculosis")
    await _project(store, "Malaria")
    results = await ListProjectsHandler(store.projects)(ListProjectsQuery())
    assert [r.name for r in results] == ["Malaria", "Tuberculosis"]


async def test_get_project(store: InMemoryStore) -> None:
    project_id = await _project(store)
    assert (await GetProjectHandler(store.projects)(GetProjectQuery(project_id))).id == project_id
    with pytest.raises(ProjectNotFoundError):
        await GetProjectHandler(store.projects)(GetProjectQuery(uuid4()))


async def test_update_project_changes_only_what_is_given(store: InMemoryStore) -> None:
    language_id = await _language(store)
    created = await CreateProjectHandler(store.projects, store.languages)(
        CreateProjectCommand(name="Malaria", description="Old", base_language_id=language_id)
    )
    update = UpdateProjectHandler(store.projects)

    renamed = await update(
        UpdateProjectCommand(created.id, name="Malaria v2", description=UNCHANGED)
    )
    assert (renamed.name, renamed.description) == ("Malaria v2", "Old")

    described = await update(UpdateProjectCommand(created.id, description="New"))
    assert (described.name, described.description) == ("Malaria v2", "New")

    cleared = await update(UpdateProjectCommand(created.id, description=None))
    assert cleared.description is None
    assert cleared.base_language_id == language_id


async def test_update_project_missing_id(store: InMemoryStore) -> None:
    with pytest.raises(ProjectNotFoundError):
        await UpdateProjectHandler(store.projects)(UpdateProjectCommand(uuid4(), name="X"))


async def test_delete_project(store: InMemoryStore) -> None:
    project_id = await _project(store)
    await DeleteProjectHandler(store.projects, store.protocols)(DeleteProjectCommand(project_id))
    assert project_id not in store.projects.rows
    with pytest.raises(ProjectNotFoundError):
        await DeleteProjectHandler(store.projects, store.protocols)(DeleteProjectCommand(uuid4()))


async def test_delete_project_with_protocols_is_a_conflict(store: InMemoryStore) -> None:
    project_id = await _project(store)
    await _protocol(store, project_id)
    with pytest.raises(ProjectHasProtocolsError):
        await DeleteProjectHandler(store.projects, store.protocols)(
            DeleteProjectCommand(project_id)
        )
    assert project_id in store.projects.rows


# --- Language guard ---


async def test_delete_language_used_as_base_language_is_a_conflict(store: InMemoryStore) -> None:
    language_id = await _language(store)
    await CreateProjectHandler(store.projects, store.languages)(
        CreateProjectCommand(name="Malaria", description=None, base_language_id=language_id)
    )
    with pytest.raises(LanguageInUseError):
        await DeleteLanguageHandler(store.languages, store.projects)(
            DeleteLanguageCommand(language_id)
        )
    assert language_id in store.languages.rows


async def test_delete_unused_language(store: InMemoryStore) -> None:
    language_id = await _language(store)
    await DeleteLanguageHandler(store.languages, store.projects)(DeleteLanguageCommand(language_id))
    assert language_id not in store.languages.rows


# --- Protocol ---


async def test_create_protocol_under_a_project(store: InMemoryStore) -> None:
    project_id = await _project(store)
    result = await CreateProtocolHandler(store.protocols, store.projects)(
        CreateProtocolCommand(project_id=project_id, name=" Triage ", description="d")
    )
    assert (result.project_id, result.name, result.description) == (project_id, "Triage", "d")


async def test_create_protocol_under_a_missing_project(store: InMemoryStore) -> None:
    with pytest.raises(ProjectNotFoundError):
        await _protocol(store, uuid4())
    assert store.protocols.rows == {}


async def test_list_protocols_returns_only_the_projects_own(store: InMemoryStore) -> None:
    project_a = await _project(store, "A")
    project_b = await _project(store, "B")
    await _protocol(store, project_a, "Zeta")
    await _protocol(store, project_a, "Alpha")
    await _protocol(store, project_b, "Other")

    results = await ListProtocolsHandler(store.protocols, store.projects)(
        ListProtocolsQuery(project_a)
    )

    assert [r.name for r in results] == ["Alpha", "Zeta"]


async def test_list_protocols_of_a_missing_project(store: InMemoryStore) -> None:
    with pytest.raises(ProjectNotFoundError):
        await ListProtocolsHandler(store.protocols, store.projects)(ListProtocolsQuery(uuid4()))


async def test_get_update_protocol(store: InMemoryStore) -> None:
    protocol_id = await _protocol(store, await _project(store))
    assert (await GetProtocolHandler(store.protocols)(GetProtocolQuery(protocol_id))).name == (
        "Triage"
    )
    updated = await UpdateProtocolHandler(store.protocols)(
        UpdateProtocolCommand(protocol_id, name="Triage v2", description="x")
    )
    assert (updated.name, updated.description) == ("Triage v2", "x")
    kept = await UpdateProtocolHandler(store.protocols)(UpdateProtocolCommand(protocol_id))
    assert (kept.name, kept.description) == ("Triage v2", "x")


async def test_protocol_missing_id(store: InMemoryStore) -> None:
    with pytest.raises(ProtocolNotFoundError):
        await GetProtocolHandler(store.protocols)(GetProtocolQuery(uuid4()))
    with pytest.raises(ProtocolNotFoundError):
        await UpdateProtocolHandler(store.protocols)(UpdateProtocolCommand(uuid4(), name="X"))
    with pytest.raises(ProtocolNotFoundError):
        await DeleteProtocolHandler(store.protocols, store.themes)(DeleteProtocolCommand(uuid4()))


async def test_delete_protocol_with_themes_is_a_conflict(store: InMemoryStore) -> None:
    protocol_id = await _protocol(store, await _project(store))
    await _theme(store, protocol_id)
    delete = DeleteProtocolHandler(store.protocols, store.themes)
    with pytest.raises(ProtocolHasThemesError):
        await delete(DeleteProtocolCommand(protocol_id))
    assert protocol_id in store.protocols.rows


async def test_delete_protocol(store: InMemoryStore) -> None:
    protocol_id = await _protocol(store, await _project(store))
    await DeleteProtocolHandler(store.protocols, store.themes)(DeleteProtocolCommand(protocol_id))
    assert protocol_id not in store.protocols.rows


# --- Theme ---


async def test_create_theme_under_a_missing_protocol(store: InMemoryStore) -> None:
    with pytest.raises(ProtocolNotFoundError):
        await _theme(store, uuid4())
    assert store.themes.rows == {}


async def test_list_themes_returns_only_the_protocols_own(store: InMemoryStore) -> None:
    project_id = await _project(store)
    protocol_a = await _protocol(store, project_id, "A")
    protocol_b = await _protocol(store, project_id, "B")
    await _theme(store, protocol_a, "Fever")
    await _theme(store, protocol_a, "Cough")
    await _theme(store, protocol_b, "Other")

    results = await ListThemesHandler(store.themes, store.protocols)(ListThemesQuery(protocol_a))

    assert [r.name for r in results] == ["Cough", "Fever"]
    assert {r.protocol_id for r in results} == {protocol_a}


async def test_list_themes_of_a_missing_protocol(store: InMemoryStore) -> None:
    with pytest.raises(ProtocolNotFoundError):
        await ListThemesHandler(store.themes, store.protocols)(ListThemesQuery(uuid4()))


async def test_theme_get_update_delete(store: InMemoryStore) -> None:
    theme_id = await _theme(store, await _protocol(store, await _project(store)))
    assert (await GetThemeHandler(store.themes)(GetThemeQuery(theme_id))).name == "Fever"
    updated = await UpdateThemeHandler(store.themes)(
        UpdateThemeCommand(theme_id, description="High temperature")
    )
    assert (updated.name, updated.description) == ("Fever", "High temperature")
    await DeleteThemeHandler(store.themes)(DeleteThemeCommand(theme_id))
    assert theme_id not in store.themes.rows


async def test_theme_missing_id(store: InMemoryStore) -> None:
    with pytest.raises(ThemeNotFoundError):
        await GetThemeHandler(store.themes)(GetThemeQuery(uuid4()))
    with pytest.raises(ThemeNotFoundError):
        await UpdateThemeHandler(store.themes)(UpdateThemeCommand(uuid4(), name="X"))
    with pytest.raises(ThemeNotFoundError):
        await DeleteThemeHandler(store.themes)(DeleteThemeCommand(uuid4()))
