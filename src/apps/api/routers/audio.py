from __future__ import annotations

from typing import Annotated
from uuid import UUID  # noqa: TC003 — FastAPI resolves path parameter annotations at runtime

from fastapi import APIRouter, Depends, Response, UploadFile, status

from apps.api.dependencies import get_container
from apps.api.schemas.audio import AudioResponse, PlaybackUrlResponse
from config.container import Container
from qa_authoring.application.delete_answer_audio.command import DeleteAnswerAudioCommand
from qa_authoring.application.delete_variant_audio.command import DeleteVariantAudioCommand
from qa_authoring.application.get_audio.command import GetAudioQuery
from qa_authoring.application.get_audio_playback_url.command import GetAudioPlaybackUrlQuery
from qa_authoring.application.set_answer_audio.command import SetAnswerAudioCommand
from qa_authoring.application.set_variant_audio.command import SetVariantAudioCommand

router = APIRouter(tags=["audio"])

ContainerDep = Annotated[Container, Depends(get_container)]


async def _read(file: UploadFile, container: Container) -> bytes:
    # One byte past the limit is enough to know it is too large, without reading it all.
    return await file.read(container.audio_policy.max_upload_bytes + 1)


def _status(response: Response, created: bool) -> None:
    if not created:
        response.status_code = status.HTTP_200_OK


@router.post("/qasets/{qaset_id}/answers/{answer_id}/audio", status_code=status.HTTP_201_CREATED)
async def set_answer_audio(
    qaset_id: UUID, answer_id: UUID, file: UploadFile, response: Response, container: ContainerDep
) -> AudioResponse:
    """Upload (multipart ``file``) the answer's recording: 201 when set, 200 when it replaced one.
    The type is detected from the bytes; 422 if unsupported or too large."""
    command = SetAnswerAudioCommand(
        qaset_id=qaset_id,
        answer_id=answer_id,
        content=await _read(file, container),
        client_mime=file.content_type,
    )
    result, created = await container.run(container.build_set_answer_audio, command)
    _status(response, created)
    return AudioResponse.of(result)


@router.delete(
    "/qasets/{qaset_id}/answers/{answer_id}/audio", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_answer_audio(qaset_id: UUID, answer_id: UUID, container: ContainerDep) -> Response:
    command = DeleteAnswerAudioCommand(qaset_id=qaset_id, answer_id=answer_id)
    await container.run(container.build_delete_answer_audio, command)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/qasets/{qaset_id}/variants/{variant_id}/audio", status_code=status.HTTP_201_CREATED)
async def set_variant_audio(
    qaset_id: UUID, variant_id: UUID, file: UploadFile, response: Response, container: ContainerDep
) -> AudioResponse:
    """Upload (multipart ``file``) the variant's recording: 201 when set, 200 when it replaced
    one."""
    command = SetVariantAudioCommand(
        qaset_id=qaset_id,
        variant_id=variant_id,
        content=await _read(file, container),
        client_mime=file.content_type,
    )
    result, created = await container.run(container.build_set_variant_audio, command)
    _status(response, created)
    return AudioResponse.of(result)


@router.delete(
    "/qasets/{qaset_id}/variants/{variant_id}/audio", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_variant_audio(
    qaset_id: UUID, variant_id: UUID, container: ContainerDep
) -> Response:
    command = DeleteVariantAudioCommand(qaset_id=qaset_id, variant_id=variant_id)
    await container.run(container.build_delete_variant_audio, command)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/audios/{audio_id}")
async def get_audio(audio_id: UUID, container: ContainerDep) -> AudioResponse:
    return AudioResponse.of(await container.run(container.build_get_audio, GetAudioQuery(audio_id)))


@router.get("/audios/{audio_id}/playback-url")
async def get_audio_playback_url(audio_id: UUID, container: ContainerDep) -> PlaybackUrlResponse:
    """A short-lived signed URL to play the recording; mint a new one when it expires."""
    query = GetAudioPlaybackUrlQuery(audio_id)
    return PlaybackUrlResponse.of(
        await container.run(container.build_get_audio_playback_url, query)
    )
