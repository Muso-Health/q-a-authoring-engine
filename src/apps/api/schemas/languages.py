from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from collections.abc import Sequence

    from qa_authoring.application.language_response import LanguageResult

# Code format and name blankness are domain rules: the domain raises and the edge maps them to 422
# (invalid_language_code / invalid_language_name), so they are not duplicated here.


class RegisterLanguageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    name: str


class UpdateLanguageRequest(BaseModel):
    """Only the name is editable; a ``code`` in the body is rejected (it is immutable)."""

    model_config = ConfigDict(extra="forbid")

    name: str


class LanguageResponse(BaseModel):
    id: UUID
    code: str
    name: str

    @classmethod
    def of(cls, result: LanguageResult) -> LanguageResponse:
        return cls(id=result.id, code=result.code, name=result.name)


class LanguagesResponse(BaseModel):
    items: list[LanguageResponse]

    @classmethod
    def of(cls, results: Sequence[LanguageResult]) -> LanguagesResponse:
        return cls(items=[LanguageResponse.of(result) for result in results])
