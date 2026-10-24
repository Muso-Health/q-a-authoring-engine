from __future__ import annotations

import asyncio
import io
import logging
from typing import TYPE_CHECKING

import docx
from pypdf import PdfReader

if TYPE_CHECKING:
    from collections.abc import Callable

    from qa_authoring.application.ports.document_storage import DocumentStoragePort
    from qa_authoring.domain.model.documentation import Documentation

_log = logging.getLogger(__name__)

DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _pdf_text(content: bytes) -> str:
    return "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(content)).pages)


def _docx_text(content: bytes) -> str:
    return "\n".join(p.text for p in docx.Document(io.BytesIO(content)).paragraphs if p.text)


def _plain_text(content: bytes) -> str:
    return content.decode("utf-8", errors="replace")


_READERS: dict[str, Callable[[bytes], str]] = {
    "application/pdf": _pdf_text,
    DOCX: _docx_text,
    "text/plain": _plain_text,
}


class TextDocumentExtractor:
    """Extracts text from PDF, Word (docx) and plain-text documents. Video and images hold no
    text it can read (a multimodal extractor is a separate adapter), nor do unreadable files."""

    def __init__(self, storage: DocumentStoragePort) -> None:
        self._storage = storage

    async def extract(self, documentation: Documentation) -> str | None:
        reader = _READERS.get(documentation.mime_type)
        if reader is None:
            return None
        content = await self._storage.read(documentation.storage_uri)
        try:
            text = await asyncio.to_thread(reader, content)
        except Exception:
            _log.warning("could not read %s", documentation.filename, exc_info=True)
            return None
        return text.strip() or None
