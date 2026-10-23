from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

from qa_authoring.application.patch import UNCHANGED, Unchanged

if TYPE_CHECKING:
    from collections.abc import Sequence

    from qa_authoring.application.catalog_response import (
        ProjectResult,
        ProtocolResult,
        ThemeResult,
    )

# Name blankness is a domain rule (422 invalid_name); unknown fields — including the immutable
# parent / base-language ids on PATCH — are rejected here (422 invalid_request).


class CreateNamedRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str | None = None


class CreateProjectRequest(CreateNamedRequest):
    base_language_id: UUID


class UpdateNamedRequest(BaseModel):
    """PATCH: an absent field is unchanged; ``description: null`` clears the description."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    description: str | None = None

    @field_validator("name")
    @classmethod
    def _name_not_null(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("name cannot be null")
        return value

    def description_change(self) -> str | Unchanged | None:
        return self.description if "description" in self.model_fields_set else UNCHANGED


class ProjectResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    base_language_id: UUID

    @classmethod
    def of(cls, result: ProjectResult) -> ProjectResponse:
        return cls(
            id=result.id,
            name=result.name,
            description=result.description,
            base_language_id=result.base_language_id,
        )


class ProjectsResponse(BaseModel):
    items: list[ProjectResponse]

    @classmethod
    def of(cls, results: Sequence[ProjectResult]) -> ProjectsResponse:
        return cls(items=[ProjectResponse.of(result) for result in results])


class ProtocolResponse(BaseModel):
    id: UUID
    project_id: UUID
    name: str
    description: str | None

    @classmethod
    def of(cls, result: ProtocolResult) -> ProtocolResponse:
        return cls(
            id=result.id,
            project_id=result.project_id,
            name=result.name,
            description=result.description,
        )


class ProtocolsResponse(BaseModel):
    items: list[ProtocolResponse]

    @classmethod
    def of(cls, results: Sequence[ProtocolResult]) -> ProtocolsResponse:
        return cls(items=[ProtocolResponse.of(result) for result in results])


class ThemeResponse(BaseModel):
    id: UUID
    protocol_id: UUID
    name: str
    description: str | None

    @classmethod
    def of(cls, result: ThemeResult) -> ThemeResponse:
        return cls(
            id=result.id,
            protocol_id=result.protocol_id,
            name=result.name,
            description=result.description,
        )


class ThemesResponse(BaseModel):
    items: list[ThemeResponse]

    @classmethod
    def of(cls, results: Sequence[ThemeResult]) -> ThemesResponse:
        return cls(items=[ThemeResponse.of(result) for result in results])
