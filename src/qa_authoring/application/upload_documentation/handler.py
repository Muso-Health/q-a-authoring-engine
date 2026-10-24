from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from qa_authoring.application.documentation_errors import (
    DocumentTooLargeError,
    UnsupportedDocumentTypeError,
)
from qa_authoring.application.documentation_policy import normalize_mime
from qa_authoring.application.documentation_response import DocumentationResult
from qa_authoring.application.theme_errors import ThemeNotFoundError
from qa_authoring.domain.model.documentation import Documentation

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime

    from qa_authoring.application.documentation_policy import DocumentationPolicy
    from qa_authoring.application.ports.document_storage import DocumentStoragePort
    from qa_authoring.application.ports.documentation_repository import DocumentationRepository
    from qa_authoring.application.ports.theme_repository import ThemeRepository
    from qa_authoring.application.upload_documentation.command import (
        UploadDocumentationCommand,
    )


class UploadDocumentationHandler:
    """Attach a document to a theme. Its type and size are checked first; the bytes are stored
    before the reference is saved, so a saved reference never points at a missing blob."""

    def __init__(
        self,
        themes: ThemeRepository,
        documentation: DocumentationRepository,
        storage: DocumentStoragePort,
        policy: DocumentationPolicy,
        clock: Callable[[], datetime],
    ) -> None:
        self._themes = themes
        self._documentation = documentation
        self._storage = storage
        self._policy = policy
        self._clock = clock

    async def __call__(self, command: UploadDocumentationCommand) -> DocumentationResult:
        if await self._themes.get(command.theme_id) is None:
            raise ThemeNotFoundError(command.theme_id)
        mime_type = normalize_mime(command.mime_type)
        if mime_type not in self._policy.allowed_mime_types:
            raise UnsupportedDocumentTypeError(mime_type)
        size = len(command.content)
        if not 0 < size <= self._policy.max_upload_bytes:
            raise DocumentTooLargeError(size, self._policy.max_upload_bytes)
        storage_uri = await self._storage.store(command.content, mime_type)
        documentation = Documentation.create(
            theme_id=command.theme_id,
            filename=command.filename,
            mime_type=mime_type,
            size_bytes=size,
            checksum_sha256=hashlib.sha256(command.content).hexdigest(),
            storage_uri=storage_uri,
            at=self._clock(),
        )
        await self._documentation.add(documentation)
        return DocumentationResult.of(documentation)
