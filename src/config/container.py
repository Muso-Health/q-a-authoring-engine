from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.create_project.handler import CreateProjectHandler
from qa_authoring.application.create_protocol.handler import CreateProtocolHandler
from qa_authoring.application.create_theme.handler import CreateThemeHandler
from qa_authoring.application.delete_language.handler import DeleteLanguageHandler
from qa_authoring.application.delete_project.handler import DeleteProjectHandler
from qa_authoring.application.delete_protocol.handler import DeleteProtocolHandler
from qa_authoring.application.delete_theme.handler import DeleteThemeHandler
from qa_authoring.application.get_language.handler import GetLanguageHandler
from qa_authoring.application.get_project.handler import GetProjectHandler
from qa_authoring.application.get_protocol.handler import GetProtocolHandler
from qa_authoring.application.get_theme.handler import GetThemeHandler
from qa_authoring.application.list_languages.handler import ListLanguagesHandler
from qa_authoring.application.list_projects.handler import ListProjectsHandler
from qa_authoring.application.list_protocols.handler import ListProtocolsHandler
from qa_authoring.application.list_themes.handler import ListThemesHandler
from qa_authoring.application.register_language.handler import RegisterLanguageHandler
from qa_authoring.application.update_language.handler import UpdateLanguageHandler
from qa_authoring.application.update_project.handler import UpdateProjectHandler
from qa_authoring.application.update_protocol.handler import UpdateProtocolHandler
from qa_authoring.application.update_theme.handler import UpdateThemeHandler

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from qa_authoring.application.ports.unit_of_work import UnitOfWork


class Container:
    """The DI container: builds each use-case handler over the repositories of a unit of work.

    ``run`` opens one unit of work per call — one transaction per use case. Framework-agnostic: the
    API edge reads it off ``app.state``. The unit-of-work factory is injected, so ``main.py`` wires
    the SQLAlchemy one and tests wire an in-memory one.
    """

    def __init__(self, unit_of_work: Callable[[], UnitOfWork]) -> None:
        self._unit_of_work = unit_of_work

    async def run[C, R](
        self,
        build: Callable[[UnitOfWork], Callable[[C], Awaitable[R]]],
        command: C,
    ) -> R:
        async with self._unit_of_work() as uow:
            return await build(uow)(command)

    def build_register_language(self, uow: UnitOfWork) -> RegisterLanguageHandler:
        return RegisterLanguageHandler(uow.languages)

    def build_list_languages(self, uow: UnitOfWork) -> ListLanguagesHandler:
        return ListLanguagesHandler(uow.languages)

    def build_get_language(self, uow: UnitOfWork) -> GetLanguageHandler:
        return GetLanguageHandler(uow.languages)

    def build_update_language(self, uow: UnitOfWork) -> UpdateLanguageHandler:
        return UpdateLanguageHandler(uow.languages)

    def build_delete_language(self, uow: UnitOfWork) -> DeleteLanguageHandler:
        return DeleteLanguageHandler(uow.languages, uow.projects)

    def build_create_project(self, uow: UnitOfWork) -> CreateProjectHandler:
        return CreateProjectHandler(uow.projects, uow.languages)

    def build_list_projects(self, uow: UnitOfWork) -> ListProjectsHandler:
        return ListProjectsHandler(uow.projects)

    def build_get_project(self, uow: UnitOfWork) -> GetProjectHandler:
        return GetProjectHandler(uow.projects)

    def build_update_project(self, uow: UnitOfWork) -> UpdateProjectHandler:
        return UpdateProjectHandler(uow.projects)

    def build_delete_project(self, uow: UnitOfWork) -> DeleteProjectHandler:
        return DeleteProjectHandler(uow.projects, uow.protocols)

    def build_create_protocol(self, uow: UnitOfWork) -> CreateProtocolHandler:
        return CreateProtocolHandler(uow.protocols, uow.projects)

    def build_list_protocols(self, uow: UnitOfWork) -> ListProtocolsHandler:
        return ListProtocolsHandler(uow.protocols, uow.projects)

    def build_get_protocol(self, uow: UnitOfWork) -> GetProtocolHandler:
        return GetProtocolHandler(uow.protocols)

    def build_update_protocol(self, uow: UnitOfWork) -> UpdateProtocolHandler:
        return UpdateProtocolHandler(uow.protocols)

    def build_delete_protocol(self, uow: UnitOfWork) -> DeleteProtocolHandler:
        return DeleteProtocolHandler(uow.protocols, uow.themes)

    def build_create_theme(self, uow: UnitOfWork) -> CreateThemeHandler:
        return CreateThemeHandler(uow.themes, uow.protocols)

    def build_list_themes(self, uow: UnitOfWork) -> ListThemesHandler:
        return ListThemesHandler(uow.themes, uow.protocols)

    def build_get_theme(self, uow: UnitOfWork) -> GetThemeHandler:
        return GetThemeHandler(uow.themes)

    def build_update_theme(self, uow: UnitOfWork) -> UpdateThemeHandler:
        return UpdateThemeHandler(uow.themes)

    def build_delete_theme(self, uow: UnitOfWork) -> DeleteThemeHandler:
        return DeleteThemeHandler(uow.themes)
