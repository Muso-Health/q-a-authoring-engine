from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from collections.abc import Sequence

    from qa_authoring.application.prompt_template_response import PromptTemplateResult


class UpdatePromptTemplateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str


class PromptTemplateResponse(BaseModel):
    """``updated_by`` is the editor's email; null for the seeded default."""

    key: str
    content: str
    required_placeholders: list[str]
    updated_by: str | None
    updated_at: datetime

    @classmethod
    def of(cls, result: PromptTemplateResult) -> PromptTemplateResponse:
        return cls(
            key=result.key,
            content=result.content,
            required_placeholders=list(result.required_placeholders),
            updated_by=result.updated_by_email,
            updated_at=result.updated_at,
        )


class PromptTemplatesResponse(BaseModel):
    items: list[PromptTemplateResponse]

    @classmethod
    def of(cls, results: Sequence[PromptTemplateResult]) -> PromptTemplatesResponse:
        return cls(items=[PromptTemplateResponse.of(result) for result in results])
