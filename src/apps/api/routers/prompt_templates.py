from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from apps.api.auth import CurrentUser, requires
from apps.api.dependencies import get_container
from apps.api.schemas.prompt_templates import (
    PromptTemplateResponse,
    PromptTemplatesResponse,
    UpdatePromptTemplateRequest,
)
from config.container import Container
from qa_authoring.application.get_prompt_template.command import GetPromptTemplateQuery
from qa_authoring.application.list_prompt_templates.command import ListPromptTemplatesQuery
from qa_authoring.application.update_prompt_template.command import (
    UpdatePromptTemplateCommand,
)
from qa_authoring.domain.model.permission import Permission

router = APIRouter(prefix="/prompt-templates", tags=["prompt templates"])

ContainerDep = Annotated[Container, Depends(get_container)]


@router.get("")
async def list_prompt_templates(container: ContainerDep) -> PromptTemplatesResponse:
    """The active template of every use, shared by everyone."""
    query = ListPromptTemplatesQuery()
    return PromptTemplatesResponse.of(
        await container.run(container.build_list_prompt_templates, query)
    )


@router.get("/{key}")
async def get_prompt_template(key: str, container: ContainerDep) -> PromptTemplateResponse:
    query = GetPromptTemplateQuery(key)
    return PromptTemplateResponse.of(
        await container.run(container.build_get_prompt_template, query)
    )


@router.put("/{key}", dependencies=[requires(Permission.MANAGE_PROMPTS)])
async def update_prompt_template(
    key: str, body: UpdatePromptTemplateRequest, user: CurrentUser, container: ContainerDep
) -> PromptTemplateResponse:
    """Replace the template for everyone. ``content`` must use exactly the key's
    ``required_placeholders`` as ``{name}``; write ``{{`` and ``}}`` for literal braces."""
    command = UpdatePromptTemplateCommand(key, body.content, actor_user_id=user.id)
    return PromptTemplateResponse.of(
        await container.run(container.build_update_prompt_template, command)
    )
