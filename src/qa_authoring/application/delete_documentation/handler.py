from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.documentation_errors import DocumentationNotFoundError

if TYPE_CHECKING:
    from qa_authoring.application.audio_upload import AfterCommit
    from qa_authoring.application.delete_documentation.command import (
        DeleteDocumentationCommand,
    )
    from qa_authoring.application.ports.document_storage import DocumentStoragePort
    from qa_authoring.application.ports.documentation_repository import DocumentationRepository


class DeleteDocumentationHandler:
    """Remove a theme's document: the reference goes in the transaction; the blob is deleted
    after the commit, unless another document still uses it (blobs are content-addressed)."""

    def __init__(
        self,
        documentation: DocumentationRepository,
        storage: DocumentStoragePort,
        after_commit: AfterCommit,
    ) -> None:
        self._documentation = documentation
        self._storage = storage
        self._after_commit = after_commit

    async def __call__(self, command: DeleteDocumentationCommand) -> None:
        document = await self._documentation.get(command.documentation_id)
        if document is None or document.theme_id != command.theme_id:
            raise DocumentationNotFoundError(command.documentation_id)
        await self._documentation.delete(document.id)
        if await self._documentation.storage_uri_in_use(document.storage_uri):
            return
        storage_uri = document.storage_uri

        async def delete_blob() -> None:
            await self._storage.delete(storage_uri)

        self._after_commit(delete_blob)
