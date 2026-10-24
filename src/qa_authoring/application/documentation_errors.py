from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID


class DocumentationNotFoundError(Exception):
    def __init__(self, documentation_id: UUID) -> None:
        super().__init__(f"documentation {documentation_id} not found")
        self.documentation_id = documentation_id


class UnsupportedDocumentTypeError(Exception):
    def __init__(self, mime_type: str) -> None:
        super().__init__(f"{mime_type or 'this file type'} is not an accepted document type")
        self.mime_type = mime_type


class DocumentTooLargeError(Exception):
    """Raised for an upload above the limit, or an empty one."""

    def __init__(self, size_bytes: int, max_bytes: int) -> None:
        super().__init__(f"the upload is {size_bytes} bytes; it must be 1 to {max_bytes}")
        self.size_bytes = size_bytes
        self.max_bytes = max_bytes
