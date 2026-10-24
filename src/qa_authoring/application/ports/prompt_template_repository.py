from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from qa_authoring.domain.model.prompt_template import PromptTemplate, PromptTemplateKey


class PromptTemplateRepository(Protocol):
    async def get(self, key: PromptTemplateKey) -> PromptTemplate | None: ...

    async def list(self) -> tuple[PromptTemplate, ...]:
        """In key order."""
        ...

    async def add(self, template: PromptTemplate) -> None: ...

    async def update(self, template: PromptTemplate) -> None: ...
