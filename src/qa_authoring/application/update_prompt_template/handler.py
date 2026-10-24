from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.prompt_templates import parse_key, template_result
from qa_authoring.domain.model.prompt_template import PromptTemplate

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime

    from qa_authoring.application.ports.prompt_template_repository import (
        PromptTemplateRepository,
    )
    from qa_authoring.application.ports.user_repository import UserRepository
    from qa_authoring.application.prompt_template_response import PromptTemplateResult
    from qa_authoring.application.update_prompt_template.command import (
        UpdatePromptTemplateCommand,
    )


class UpdatePromptTemplateHandler:
    """Replace the active template of a fixed key, for everyone. Keys are never created by
    users; one that was never seeded gets its row on first save."""

    def __init__(
        self,
        templates: PromptTemplateRepository,
        users: UserRepository,
        clock: Callable[[], datetime],
    ) -> None:
        self._templates = templates
        self._users = users
        self._clock = clock

    async def __call__(self, command: UpdatePromptTemplateCommand) -> PromptTemplateResult:
        key = parse_key(command.key)
        template = await self._templates.get(key)
        if template is None:
            template = PromptTemplate.create(
                key, command.content, updated_by=command.actor_user_id, at=self._clock()
            )
            await self._templates.add(template)
        else:
            template.revise(command.content, updated_by=command.actor_user_id, at=self._clock())
            await self._templates.update(template)
        return await template_result(self._users, template)
