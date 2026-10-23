from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from qa_authoring.application.language_errors import LanguageInUseError
from qa_authoring.application.project_errors import (
    ProjectHasProtocolsError,
    ProjectNotFoundError,
    UnknownBaseLanguageError,
)
from qa_authoring.application.protocol_errors import (
    ProtocolHasThemesError,
    ProtocolNotFoundError,
)
from qa_authoring.domain.model.language import Language
from qa_authoring.domain.model.project import Project
from qa_authoring.domain.model.protocol import Protocol
from qa_authoring.domain.model.theme import Theme
from qa_authoring.domain.value_objects.language_code import LanguageCode
from qa_authoring.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

pytestmark = pytest.mark.integration


async def _seed(engine: AsyncEngine) -> tuple[Language, Project, Protocol, Theme]:
    language = Language.register(LanguageCode("fr"), "French")
    project = Project.create(name="Malaria", base_language_id=language.id, description="CHW")
    protocol = Protocol.create(project_id=project.id, name="Triage")
    theme = Theme.create(protocol_id=protocol.id, name="Fever", description="High temperature")
    async with SqlAlchemyUnitOfWork(engine) as uow:
        await uow.languages.add(language)
        await uow.projects.add(project)
        await uow.protocols.add(protocol)
        await uow.themes.add(theme)
    return language, project, protocol, theme


async def test_round_trips_the_catalog(migrated_engine: AsyncEngine) -> None:
    language, project, protocol, theme = await _seed(migrated_engine)

    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        loaded_project = await uow.projects.get(project.id)
        loaded_protocol = await uow.protocols.get(protocol.id)
        loaded_theme = await uow.themes.get(theme.id)
        projects = await uow.projects.list()
        protocols = await uow.protocols.list_by_project(project.id)
        themes = await uow.themes.list_by_protocol(protocol.id)
        assert await uow.projects.uses_base_language(language.id)
        assert await uow.protocols.exists_for_project(project.id)
        assert await uow.themes.exists_for_protocol(protocol.id)
        assert not await uow.protocols.exists_for_project(uuid4())

    assert loaded_project is not None
    assert (loaded_project.name, loaded_project.description, loaded_project.base_language_id) == (
        "Malaria",
        "CHW",
        language.id,
    )
    assert loaded_protocol is not None
    assert (loaded_protocol.project_id, loaded_protocol.name, loaded_protocol.description) == (
        project.id,
        "Triage",
        None,
    )
    assert loaded_theme is not None
    assert (loaded_theme.protocol_id, loaded_theme.name, loaded_theme.description) == (
        protocol.id,
        "Fever",
        "High temperature",
    )
    assert projects == (project,)
    assert protocols == (protocol,)
    assert themes == (theme,)


async def test_updates_name_and_description(migrated_engine: AsyncEngine) -> None:
    _, project, protocol, theme = await _seed(migrated_engine)
    for entity in (project, protocol, theme):
        entity.rename(f"{entity.name} v2")
        entity.describe(None)
    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        await uow.projects.update(project)
        await uow.protocols.update(protocol)
        await uow.themes.update(theme)

    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        loaded = [
            await uow.projects.get(project.id),
            await uow.protocols.get(protocol.id),
            await uow.themes.get(theme.id),
        ]
    assert [(e.name, e.description) for e in loaded if e is not None] == [
        ("Malaria v2", None),
        ("Triage v2", None),
        ("Fever v2", None),
    ]


async def test_deletes_bottom_up(migrated_engine: AsyncEngine) -> None:
    language, project, protocol, theme = await _seed(migrated_engine)
    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        await uow.themes.delete(theme.id)
        await uow.protocols.delete(protocol.id)
        await uow.projects.delete(project.id)
        await uow.languages.delete(language.id)
    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        assert await uow.projects.list() == ()
        assert await uow.languages.list() == ()


async def test_fk_restrict_maps_to_conflicts(migrated_engine: AsyncEngine) -> None:
    language, project, protocol, _ = await _seed(migrated_engine)

    with pytest.raises(LanguageInUseError):
        async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
            await uow.languages.delete(language.id)
    with pytest.raises(ProjectHasProtocolsError):
        async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
            await uow.projects.delete(project.id)
    with pytest.raises(ProtocolHasThemesError):
        async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
            await uow.protocols.delete(protocol.id)

    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        assert await uow.languages.get(language.id) is not None
        assert await uow.projects.get(project.id) is not None
        assert await uow.protocols.get(protocol.id) is not None


async def test_fk_on_insert_maps_to_missing_parent(migrated_engine: AsyncEngine) -> None:
    with pytest.raises(UnknownBaseLanguageError):
        async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
            await uow.projects.add(Project.create(name="M", base_language_id=uuid4()))
    with pytest.raises(ProjectNotFoundError):
        async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
            await uow.protocols.add(Protocol.create(project_id=uuid4(), name="P"))
    with pytest.raises(ProtocolNotFoundError):
        async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
            await uow.themes.add(Theme.create(protocol_id=uuid4(), name="T"))
