from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.delete_language.handler import DeleteLanguageHandler
from qa_authoring.application.get_language.handler import GetLanguageHandler
from qa_authoring.application.list_languages.handler import ListLanguagesHandler
from qa_authoring.application.register_language.handler import RegisterLanguageHandler
from qa_authoring.application.update_language.handler import UpdateLanguageHandler

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
        return DeleteLanguageHandler(uow.languages)
