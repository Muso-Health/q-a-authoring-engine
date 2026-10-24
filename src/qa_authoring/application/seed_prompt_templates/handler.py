from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.domain.model.prompt_template import (
    DEFAULT_TEMPLATES,
    PromptTemplate,
    PromptTemplateKey,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime

    from qa_authoring.application.ports.prompt_template_repository import (
        PromptTemplateRepository,
    )
    from qa_authoring.application.seed_prompt_templates.command import (
        SeedPromptTemplatesCommand,
    )


class SeedPromptTemplatesHandler:
    """Give every key without a template its default, so prompts work before anyone edits
    them. Idempotent, and never overwrites an existing (possibly edited) template."""

    def __init__(self, templates: PromptTemplateRepository, clock: Callable[[], datetime]) -> None:
        self._templates = templates
        self._clock = clock

    async def __call__(self, command: SeedPromptTemplatesCommand) -> None:
        for key in PromptTemplateKey:
            if await self._templates.get(key) is None:
                default = DEFAULT_TEMPLATES[key]
                await self._templates.add(
                    PromptTemplate.create(key, default, updated_by=None, at=self._clock())
                )
