from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Mapping

    from qa_authoring.domain.model.prompt_template import PromptTemplateKey


class PromptTemplatePort(Protocol):
    """What translation and variant generation read prompts through."""

    async def render(self, key: PromptTemplateKey, values: Mapping[str, str]) -> str:
        """The active template for ``key`` with ``values`` substituted. Raises
        ``PromptTemplateNotFoundError`` without a template and ``PromptRenderError`` when the
        values do not match its placeholders."""
        ...
