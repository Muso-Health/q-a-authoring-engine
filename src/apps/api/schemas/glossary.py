from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

from qa_authoring.application.create_glossary_term.command import GlossaryFormInput
from qa_authoring.application.patch import UNCHANGED, Unchanged

if TYPE_CHECKING:
    from qa_authoring.application.glossary_response import (
        GlossaryFormResult,
        GlossaryTermPage,
        GlossaryTermResult,
    )

# Blank labels and preferred forms are domain rules (422 invalid_glossary_field, naming the
# field); unknown fields are rejected here (422 invalid_request).


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GlossaryFormRequest(_Strict):
    preferred: str
    synonyms: list[str] = []
    avoid: list[str] = []
    note: str | None = None


class InitialGlossaryFormRequest(GlossaryFormRequest):
    language_id: UUID

    def to_input(self) -> GlossaryFormInput:
        return GlossaryFormInput(
            self.language_id, self.preferred, tuple(self.synonyms), tuple(self.avoid), self.note
        )


class CreateGlossaryTermRequest(_Strict):
    label: str
    note: str | None = None
    forms: list[InitialGlossaryFormRequest] = []


class UpdateGlossaryTermRequest(_Strict):
    """PATCH: an absent field is unchanged; ``note: null`` clears the note."""

    label: str | None = None
    note: str | None = None

    @field_validator("label")
    @classmethod
    def _label_not_null(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("label cannot be null")
        return value

    def note_change(self) -> str | Unchanged | None:
        return self.note if "note" in self.model_fields_set else UNCHANGED


class GlossaryFormResponse(BaseModel):
    id: UUID
    language_id: UUID
    preferred: str
    synonyms: list[str]
    avoid: list[str]
    note: str | None

    @classmethod
    def of(cls, result: GlossaryFormResult) -> GlossaryFormResponse:
        return cls(
            id=result.id,
            language_id=result.language_id,
            preferred=result.preferred,
            synonyms=list(result.synonyms),
            avoid=list(result.avoid),
            note=result.note,
        )


class GlossaryTermResponse(BaseModel):
    id: UUID
    label: str
    note: str | None
    status: str
    created_at: datetime
    updated_at: datetime
    forms: list[GlossaryFormResponse]

    @classmethod
    def of(cls, result: GlossaryTermResult) -> GlossaryTermResponse:
        return cls(
            id=result.id,
            label=result.label,
            note=result.note,
            status=result.status.value,
            created_at=result.created_at,
            updated_at=result.updated_at,
            forms=[GlossaryFormResponse.of(f) for f in result.forms],
        )


class GlossaryTermsResponse(BaseModel):
    items: list[GlossaryTermResponse]
    total: int

    @classmethod
    def of(cls, page: GlossaryTermPage) -> GlossaryTermsResponse:
        return cls(items=[GlossaryTermResponse.of(t) for t in page.items], total=page.total)
