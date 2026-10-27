from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID  # noqa: TC003 — a field type on a frozen dataclass


@dataclass(frozen=True, slots=True)
class GlossaryFormInput:
    language_id: UUID
    preferred: str
    synonyms: tuple[str, ...] = ()
    avoid: tuple[str, ...] = ()
    note: str | None = None


@dataclass(frozen=True, slots=True)
class CreateGlossaryTermCommand:
    """``forms`` are put in order, so a language given twice keeps its last form."""

    label: str
    note: str | None = None
    forms: tuple[GlossaryFormInput, ...] = ()
