from __future__ import annotations

from typing import Annotated
from uuid import UUID  # noqa: TC003 — FastAPI resolves path parameter annotations at runtime

from fastapi import APIRouter, Depends, Response, status

from apps.api.dependencies import get_container
from apps.api.schemas.categories import (
    CategoriesResponse,
    CategoryResponse,
    RegisterCategoryRequest,
)
from config.container import Container
from qa_authoring.application.delete_category.command import DeleteCategoryCommand
from qa_authoring.application.get_category.command import GetCategoryQuery
from qa_authoring.application.list_categories.command import ListCategoriesQuery
from qa_authoring.application.register_category.command import RegisterCategoryCommand

router = APIRouter(prefix="/categories", tags=["categories"])

ContainerDep = Annotated[Container, Depends(get_container)]


@router.post("", status_code=status.HTTP_201_CREATED)
async def register_category(
    body: RegisterCategoryRequest, response: Response, container: ContainerDep
) -> CategoryResponse:
    """Get-or-create by normalized name (case and whitespace insensitive): 201 when created,
    200 with the existing category otherwise."""
    command = RegisterCategoryCommand(body.name)
    result, created = await container.run(container.build_register_category, command)
    if not created:
        response.status_code = status.HTTP_200_OK
    return CategoryResponse.of(result)


@router.get("")
async def list_categories(container: ContainerDep, q: str | None = None) -> CategoriesResponse:
    """The catalogue ordered by normalized name; ``q`` keeps names starting with it."""
    query = ListCategoriesQuery(prefix=q)
    return CategoriesResponse.of(await container.run(container.build_list_categories, query))


@router.get("/{category_id}")
async def get_category(category_id: UUID, container: ContainerDep) -> CategoryResponse:
    query = GetCategoryQuery(category_id)
    return CategoryResponse.of(await container.run(container.build_get_category, query))


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(category_id: UUID, container: ContainerDep) -> Response:
    """409 while any QA set has the category attached."""
    await container.run(container.build_delete_category, DeleteCategoryCommand(category_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
