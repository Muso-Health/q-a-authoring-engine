from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.prompt_templates import template_result

if TYPE_CHECKING:
    from qa_authoring.application.list_prompt_templates.command import ListPromptTemplatesQuery
    from qa_authoring.application.ports.prompt_template_repository import (
        PromptTemplateRepository,
    )
    from qa_authoring.application.ports.user_repository import UserRepository
    from qa_authoring.application.prompt_template_response import PromptTemplateResult


class ListPromptTemplatesHandler:
    def __init__(self, templates: PromptTemplateRepository, users: UserRepository) -> None:
        self._templates = templates
        self._users = users

    async def __call__(self, query: ListPromptTemplatesQuery) -> tuple[PromptTemplateResult, ...]:
        return tuple([await template_result(self._users, t) for t in await self._templates.list()])
