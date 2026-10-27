from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime  # noqa: TC003 — a field type on a frozen result dataclass
from typing import TYPE_CHECKING
from uuid import UUID  # noqa: TC003 — a field type on a frozen result dataclass

from qa_authoring.domain.model.glossary import GlossaryStatus  # noqa: TC001 — a field type

if TYPE_CHECKING:
    from qa_authoring.domain.model.glossary import GlossaryForm, GlossaryTerm


@dataclass(frozen=True, slots=True)
class GlossaryFormResult:
    id: UUID
    language_id: UUID
    preferred: str
    synonyms: tuple[str, ...]
    avoid: tuple[str, ...]
    note: str | None

    @classmethod
    def of(cls, form: GlossaryForm) -> GlossaryFormResult:
        return cls(form.id, form.language_id, form.preferred, form.synonyms, form.avoid, form.note)


@dataclass(frozen=True, slots=True)
class GlossaryTermResult:
    id: UUID
    label: str
    note: str | None
    status: GlossaryStatus
    created_at: datetime
    updated_at: datetime
    forms: tuple[GlossaryFormResult, ...]

    @classmethod
    def of(cls, term: GlossaryTerm) -> GlossaryTermResult:
        return cls(
            term.id,
            term.label,
            term.note,
            term.status,
            term.created_at,
            term.updated_at,
            tuple(GlossaryFormResult.of(f) for f in term.forms),
        )


@dataclass(frozen=True, slots=True)
class GlossaryTermPage:
    """One page of terms and the count of every match."""

    items: tuple[GlossaryTermResult, ...]
    total: int
