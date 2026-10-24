from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from collections.abc import Sequence

    from qa_authoring.application.category_response import CategoryResult


class RegisterCategoryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str


class CategoryResponse(BaseModel):
    id: UUID
    name: str

    @classmethod
    def of(cls, result: CategoryResult) -> CategoryResponse:
        return cls(id=result.id, name=result.name)


class CategoriesResponse(BaseModel):
    items: list[CategoryResponse]

    @classmethod
    def of(cls, results: Sequence[CategoryResult]) -> CategoriesResponse:
        return cls(items=[CategoryResponse.of(result) for result in results])
