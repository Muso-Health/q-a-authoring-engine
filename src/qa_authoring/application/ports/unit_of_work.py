from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, Self

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from types import TracebackType

    from qa_authoring.application.ports.category_repository import CategoryRepository
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


class UnitOfWork(Protocol):
    """One transaction: the repositories enlisted on it commit together on a clean exit and roll
    back together on an exception."""

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

    def after_commit(self, action: Callable[[], Awaitable[None]]) -> None:
        """Run ``action`` once the transaction has committed; best-effort, never rolled back.
        Skipped entirely if the transaction rolls back."""
        ...

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...
