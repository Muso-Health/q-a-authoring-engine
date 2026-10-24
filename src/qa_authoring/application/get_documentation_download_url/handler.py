from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from qa_authoring.application.documentation_errors import DocumentationNotFoundError
from qa_authoring.application.documentation_response import DownloadUrlResult

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime

    from qa_authoring.application.documentation_policy import DocumentationPolicy
    from qa_authoring.application.get_documentation_download_url.command import (
        GetDocumentationDownloadUrlQuery,
    )
    from qa_authoring.application.ports.document_storage import DocumentStoragePort
    from qa_authoring.application.ports.documentation_repository import DocumentationRepository


class GetDocumentationDownloadUrlHandler:
    """A short-lived signed URL for downloading the document, minted on demand."""

    def __init__(
        self,
        documentation: DocumentationRepository,
        storage: DocumentStoragePort,
        policy: DocumentationPolicy,
        clock: Callable[[], datetime],
    ) -> None:
        self._documentation = documentation
        self._storage = storage
        self._policy = policy
        self._clock = clock

    async def __call__(self, query: GetDocumentationDownloadUrlQuery) -> DownloadUrlResult:
        document = await self._documentation.get(query.documentation_id)
        if document is None:
            raise DocumentationNotFoundError(query.documentation_id)
        ttl = self._policy.download_url_ttl_seconds
        url = await self._storage.signed_url(document.storage_uri, ttl)
        return DownloadUrlResult(url, self._clock() + timedelta(seconds=ttl))
