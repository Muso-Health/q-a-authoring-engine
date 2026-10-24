from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime  # noqa: TC003 — a field type on a frozen result dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from qa_authoring.domain.model.prompt_template import PromptTemplate


@dataclass(frozen=True, slots=True)
class PromptTemplateResult:
    key: str
    content: str
    required_placeholders: tuple[str, ...]
    updated_by_email: str | None
    updated_at: datetime

    @classmethod
    def of(cls, template: PromptTemplate, updated_by_email: str | None) -> PromptTemplateResult:
        """``updated_by_email`` is None for the seeded default."""
        return cls(
            template.key.value,
            template.content,
            tuple(sorted(template.required_placeholders)),
            updated_by_email,
            template.updated_at,
        )
