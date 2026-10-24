from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.prompt_template_errors import PromptTemplateNotFoundError
from qa_authoring.application.prompt_template_response import PromptTemplateResult
from qa_authoring.domain.model.prompt_template import PromptTemplateKey

if TYPE_CHECKING:
    from collections.abc import Mapping

    from qa_authoring.application.ports.prompt_template_repository import (
        PromptTemplateRepository,
    )
    from qa_authoring.application.ports.user_repository import UserRepository
    from qa_authoring.domain.model.prompt_template import PromptTemplate


def parse_key(key: str) -> PromptTemplateKey:
    try:
        return PromptTemplateKey(key)
    except ValueError as exc:
        raise PromptTemplateNotFoundError(key) from exc


async def load_template(
    templates: PromptTemplateRepository, key: PromptTemplateKey
) -> PromptTemplate:
    template = await templates.get(key)
    if template is None:
        raise PromptTemplateNotFoundError(key.value)
    return template


async def template_result(users: UserRepository, template: PromptTemplate) -> PromptTemplateResult:
    editor = None if template.updated_by is None else await users.get(template.updated_by)
    return PromptTemplateResult.of(template, None if editor is None else editor.email)


class PromptRenderer:
    """The prompt-template port over the store: renders the active template of a key."""

    def __init__(self, templates: PromptTemplateRepository) -> None:
        self._templates = templates

    async def render(self, key: PromptTemplateKey, values: Mapping[str, str]) -> str:
        return (await load_template(self._templates, key)).render(values)
