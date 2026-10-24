from __future__ import annotations

import hashlib
import io
from uuid import uuid4

import docx
import pytest

from qa_authoring.domain.model.documentation import Documentation
from qa_authoring.infrastructure.extraction.text_extractor import TextDocumentExtractor
from tests.fakes import DOCX, NOW, InMemoryBlobStorage


def _pdf(text: str) -> bytes:
    """A minimal one-page PDF with ``text`` in Helvetica, built by hand (no PDF writer needed)."""
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = io.BytesIO(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(out.tell())
        out.write(f"{number} 0 obj\n".encode() + body + b"\nendobj\n")
    xref = out.tell()
    out.write(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for offset in offsets:
        out.write(f"{offset:010d} 00000 n \n".encode())
    out.write(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
    )
    return out.getvalue()


def _docx(*paragraphs: str) -> bytes:
    document = docx.Document()
    for paragraph in paragraphs:
        document.add_paragraph(paragraph)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


async def _extract(content: bytes, mime: str, filename: str = "doc") -> str | None:
    storage = InMemoryBlobStorage("documentation")
    uri = await storage.store(content, mime)
    documentation = Documentation.create(
        theme_id=uuid4(),
        filename=filename,
        mime_type=mime,
        size_bytes=len(content),
        checksum_sha256=hashlib.sha256(content).hexdigest(),
        storage_uri=uri,
        at=NOW,
    )
    return await TextDocumentExtractor(storage).extract(documentation)


async def test_extracts_pdf_text() -> None:
    text = await _extract(_pdf("Malaria causes fever."), "application/pdf")
    assert text is not None
    assert "Malaria causes fever." in text


async def test_extracts_docx_paragraphs() -> None:
    text = await _extract(_docx("Malaria causes fever.", "Use a bed net."), DOCX)
    assert text == "Malaria causes fever.\nUse a bed net."


async def test_extracts_plain_text() -> None:
    assert await _extract(b"Buvez de l'eau.\n", "text/plain") == "Buvez de l'eau."


@pytest.mark.parametrize("mime", ["video/mp4", "image/png"])
async def test_media_is_not_extractable_yet(mime: str) -> None:
    assert await _extract(b"\x00\x01binary", mime) is None


@pytest.mark.parametrize(
    ("content", "mime"),
    [(b"not a pdf", "application/pdf"), (b"not a docx", DOCX), (b"   ", "text/plain")],
)
async def test_unreadable_or_empty_documents_yield_nothing(content: bytes, mime: str) -> None:
    assert await _extract(content, mime) is None
