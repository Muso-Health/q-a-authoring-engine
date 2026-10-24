from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Self

from qa_authoring.infrastructure.persistence.repositories.category import (
    PostgresCategoryRepository,
)
from qa_authoring.infrastructure.persistence.repositories.documentation import (
    PostgresDocumentationRepository,
)
from qa_authoring.infrastructure.persistence.repositories.intent import PostgresIntentRepository
from qa_authoring.infrastructure.persistence.repositories.language import (
    PostgresLanguageRepository,
)
from qa_authoring.infrastructure.persistence.repositories.project import PostgresProjectRepository
from qa_authoring.infrastructure.persistence.repositories.prompt_template import (
    PostgresPromptTemplateRepository,
)
from qa_authoring.infrastructure.persistence.repositories.protocol import (
    PostgresProtocolRepository,
)
from qa_authoring.infrastructure.persistence.repositories.qaset import PostgresQASetRepository
from qa_authoring.infrastructure.persistence.repositories.role import PostgresRoleRepository
from qa_authoring.infrastructure.persistence.repositories.theme import PostgresThemeRepository
from qa_authoring.infrastructure.persistence.repositories.user import PostgresUserRepository
from qa_authoring.infrastructure.persistence.repositories.validation import (
    PostgresValidationRepository,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from types import TracebackType

    from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncTransaction

    from qa_authoring.application.ports.category_repository import CategoryRepository
    from qa_authoring.application.ports.documentation_repository import (
        DocumentationRepository,
    )
    from qa_authoring.application.ports.intent_repository import IntentRepository
    from qa_authoring.application.ports.language_repository import LanguageRepository
    from qa_authoring.application.ports.project_repository import ProjectRepository
    from qa_authoring.application.ports.prompt_template_repository import (
        PromptTemplateRepository,
    )
    from qa_authoring.application.ports.protocol_repository import ProtocolRepository
    from qa_authoring.application.ports.qaset_repository import QASetRepository
    from qa_authoring.application.ports.role_repository import RoleRepository
    from qa_authoring.application.ports.theme_repository import ThemeRepository
    from qa_authoring.application.ports.user_repository import UserRepository
    from qa_authoring.application.ports.validation_repository import ValidationRepository

_log = logging.getLogger(__name__)


class SqlAlchemyUnitOfWork:
    """One connection and one transaction per use case; every repository is enlisted on it.
    Commits on a clean exit, rolls back on an exception."""

    languages: LanguageRepository
    projects: ProjectRepository
    protocols: ProtocolRepository
    themes: ThemeRepository
    qasets: QASetRepository
    intents: IntentRepository
    categories: CategoryRepository
    users: UserRepository
    roles: RoleRepository
    validations: ValidationRepository
    prompt_templates: PromptTemplateRepository
    documentation: DocumentationRepository

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._connection: AsyncConnection | None = None
        self._transaction: AsyncTransaction | None = None
        self._after_commit: list[Callable[[], Awaitable[None]]] = []

    def after_commit(self, action: Callable[[], Awaitable[None]]) -> None:
        self._after_commit.append(action)

    async def __aenter__(self) -> Self:
        self._connection = await self._engine.connect()
        self._transaction = await self._connection.begin()
        self.languages = PostgresLanguageRepository(self._connection)
        self.projects = PostgresProjectRepository(self._connection)
        self.protocols = PostgresProtocolRepository(self._connection)
        self.themes = PostgresThemeRepository(self._connection)
        self.qasets = PostgresQASetRepository(self._connection)
        self.intents = PostgresIntentRepository(self._connection)
        self.categories = PostgresCategoryRepository(self._connection)
        self.users = PostgresUserRepository(self._connection)
        self.roles = PostgresRoleRepository(self._connection)
        self.validations = PostgresValidationRepository(self._connection)
        self.prompt_templates = PostgresPromptTemplateRepository(self._connection)
        self.documentation = PostgresDocumentationRepository(self._connection)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        assert self._connection is not None and self._transaction is not None
        try:
            if exc_type is None:
                await self._transaction.commit()
            else:
                await self._transaction.rollback()
                return
        finally:
            await self._connection.close()
        for action in self._after_commit:
            try:
                await action()
            except Exception:
                # Best-effort by contract: the transaction is already committed.
                _log.warning("after-commit action failed", exc_info=True)
