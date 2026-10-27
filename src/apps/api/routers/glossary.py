from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID  # noqa: TC003 — FastAPI resolves path parameter annotations at runtime

from fastapi import APIRouter, Depends, Query, Response, status

from apps.api.auth import requires
from apps.api.dependencies import get_container
from apps.api.schemas.glossary import (
    CreateGlossaryTermRequest,
    GlossaryFormRequest,
    GlossaryTermResponse,
    GlossaryTermsResponse,
    UpdateGlossaryTermRequest,
)
from config.container import Container
from qa_authoring.application.archive_glossary_term.command import ArchiveGlossaryTermCommand
from qa_authoring.application.create_glossary_term.command import CreateGlossaryTermCommand
from qa_authoring.application.get_glossary_term.command import GetGlossaryTermQuery
from qa_authoring.application.list_glossary_terms.command import (
    MAX_GLOSSARY_PAGE,
    ListGlossaryTermsQuery,
)
from qa_authoring.application.remove_glossary_form.command import RemoveGlossaryFormCommand
from qa_authoring.application.unarchive_glossary_term.command import (
    UnarchiveGlossaryTermCommand,
)
from qa_authoring.application.update_glossary_term.command import UpdateGlossaryTermCommand
from qa_authoring.application.upsert_glossary_form.command import UpsertGlossaryFormCommand
from qa_authoring.domain.model.glossary import GlossaryStatus
from qa_authoring.domain.model.permission import Permission

router = APIRouter(prefix="/glossary/terms", tags=["glossary"])

ContainerDep = Annotated[Container, Depends(get_container)]

_MANAGE = requires(Permission.MANAGE_GLOSSARY)


@router.post("", status_code=status.HTTP_201_CREATED, dependencies=[_MANAGE])
async def create_glossary_term(
    body: CreateGlossaryTermRequest, container: ContainerDep
) -> GlossaryTermResponse:
    """A term with its optional first forms (one per language; a repeated language keeps its
    last form). 404 ``language_not_found``; 422 ``invalid_glossary_field`` naming the field."""
    command = CreateGlossaryTermCommand(
        body.label, body.note, tuple(f.to_input() for f in body.forms)
    )
    return GlossaryTermResponse.of(
        await container.run(container.build_create_glossary_term, command)
    )


@router.get("")
async def list_glossary_terms(
    container: ContainerDep,
    status: Literal["active", "archived", "all"] = "active",
    q: str | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_GLOSSARY_PAGE)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> GlossaryTermsResponse:
    """Terms ordered by label (case-insensitive) with their forms, and the count of every match.
    ``q`` matches inside the label or any preferred form, synonym or form to avoid, ignoring case
    and accents."""
    query = ListGlossaryTermsQuery(
        status=None if status == "all" else GlossaryStatus(status),
        search=q,
        limit=limit,
        offset=offset,
    )
    return GlossaryTermsResponse.of(await container.run(container.build_list_glossary_terms, query))


@router.get("/{term_id}")
async def get_glossary_term(term_id: UUID, container: ContainerDep) -> GlossaryTermResponse:
    query = GetGlossaryTermQuery(term_id)
    return GlossaryTermResponse.of(await container.run(container.build_get_glossary_term, query))


@router.patch("/{term_id}", dependencies=[_MANAGE])
async def update_glossary_term(
    term_id: UUID, body: UpdateGlossaryTermRequest, container: ContainerDep
) -> GlossaryTermResponse:
    """Change the label and/or the note (``note: null`` clears it)."""
    command = UpdateGlossaryTermCommand(term_id, body.label, body.note_change())
    return GlossaryTermResponse.of(
        await container.run(container.build_update_glossary_term, command)
    )


@router.post("/{term_id}/archive", dependencies=[_MANAGE])
async def archive_glossary_term(term_id: UUID, container: ContainerDep) -> GlossaryTermResponse:
    """Hide the term from the default (active) listing. Idempotent."""
    command = ArchiveGlossaryTermCommand(term_id)
    return GlossaryTermResponse.of(
        await container.run(container.build_archive_glossary_term, command)
    )


@router.post("/{term_id}/unarchive", dependencies=[_MANAGE])
async def unarchive_glossary_term(term_id: UUID, container: ContainerDep) -> GlossaryTermResponse:
    """Idempotent."""
    command = UnarchiveGlossaryTermCommand(term_id)
    return GlossaryTermResponse.of(
        await container.run(container.build_unarchive_glossary_term, command)
    )


@router.put(
    "/{term_id}/forms/{language_id}",
    status_code=status.HTTP_201_CREATED,
    dependencies=[_MANAGE],
)
async def upsert_glossary_form(
    term_id: UUID,
    language_id: UUID,
    body: GlossaryFormRequest,
    response: Response,
    container: ContainerDep,
) -> GlossaryTermResponse:
    """Set the term's form in the language: 201 when it had none, 200 when it replaced it (the
    form keeps its id). Synonyms and forms to avoid are trimmed, blanks and repeats dropped.
    Returns the term."""
    command = UpsertGlossaryFormCommand(
        term_id, language_id, body.preferred, tuple(body.synonyms), tuple(body.avoid), body.note
    )
    result, created = await container.run(container.build_upsert_glossary_form, command)
    if not created:
        response.status_code = status.HTTP_200_OK
    return GlossaryTermResponse.of(result)


@router.delete(
    "/{term_id}/forms/{language_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[_MANAGE],
)
async def remove_glossary_form(
    term_id: UUID, language_id: UUID, container: ContainerDep
) -> Response:
    """404 ``glossary_form_not_found`` if the term has no form in the language."""
    command = RemoveGlossaryFormCommand(term_id, language_id)
    await container.run(container.build_remove_glossary_form, command)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
