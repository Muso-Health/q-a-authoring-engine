from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.prompt_templates import load_template, parse_key, template_result

if TYPE_CHECKING:
    from qa_authoring.application.get_prompt_template.command import GetPromptTemplateQuery
    from qa_authoring.application.ports.prompt_template_repository import (
        PromptTemplateRepository,
    )
    from qa_authoring.application.ports.user_repository import UserRepository
    from qa_authoring.application.prompt_template_response import PromptTemplateResult


class GetPromptTemplateHandler:
    def __init__(self, templates: PromptTemplateRepository, users: UserRepository) -> None:
        self._templates = templates
        self._users = users

    async def __call__(self, query: GetPromptTemplateQuery) -> PromptTemplateResult:
        template = await load_template(self._templates, parse_key(query.key))
        return await template_result(self._users, template)
