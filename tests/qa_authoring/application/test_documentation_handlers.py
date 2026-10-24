from __future__ import annotations

import hashlib
from datetime import timedelta
from uuid import UUID, uuid4

import pytest

from qa_authoring.application.delete_documentation.command import DeleteDocumentationCommand
from qa_authoring.application.documentation_errors import (
    DocumentationNotFoundError,
    DocumentTooLargeError,
    UnsupportedDocumentTypeError,
)
from qa_authoring.application.get_documentation_download_url.command import (
    GetDocumentationDownloadUrlQuery,
)
from qa_authoring.application.list_documentation.command import ListDocumentationQuery
from qa_authoring.application.theme_errors import ThemeNotFoundError
from qa_authoring.application.upload_documentation.command import UploadDocumentationCommand
from qa_authoring.domain.model.documentation import Documentation, InvalidDocumentationError
from qa_authoring.domain.model.theme import Theme
from tests.fakes import DOCX, NOW, in_memory_container

PDF = b"%PDF-1.4 tiny"


def _uri(content: bytes) -> str:
    return f"memory://documentation/{hashlib.sha256(content).hexdigest()}"


class World:
    def __init__(self) -> None:
        self.container, self.store = in_memory_container()
        theme = Theme.create(protocol_id=uuid4(), name="Malaria")
        self.store.themes.rows[theme.id] = theme
        self.theme_id = theme.id

    async def upload(
        self,
        content: bytes = PDF,
        filename: str = "guide.pdf",
        mime: str = "application/pdf",
        theme_id: UUID | None = None,
    ) -> UUID:
        c = self.container
        result = await c.run(
            c.build_upload_documentation,
            UploadDocumentationCommand(theme_id or self.theme_id, content, filename, mime),
        )
        return result.id


@pytest.fixture
def world() -> World:
    return World()


def test_documentation_values_are_validated() -> None:
    def make(**overrides: object) -> Documentation:
        values: dict[str, object] = {
            "theme_id": uuid4(),
            "filename": "a.pdf",
            "mime_type": "application/pdf",
            "size_bytes": 1,
            "checksum_sha256": "a" * 64,
            "storage_uri": "memory://x",
            "at": NOW,
        }
        values.update(overrides)
        return Documentation.create(**values)  # type: ignore[arg-type]

    assert make(filename="  C:\\docs\\../guide.pdf ").filename == "guide.pdf"
    assert make(filename="   ").filename == "document"
    for bad in (
        {"size_bytes": 0},
        {"checksum_sha256": "x"},
        {"storage_uri": ""},
        {"mime_type": "pdf"},
    ):
        with pytest.raises(InvalidDocumentationError):
            make(**bad)


async def test_upload_stores_the_blob_before_the_reference(world: World) -> None:
    doc_id = await world.upload(mime="Application/PDF; charset=binary")

    stored = world.store.documentation.rows[doc_id]
    assert (stored.theme_id, stored.filename, stored.mime_type, stored.size_bytes) == (
        world.theme_id,
        "guide.pdf",
        "application/pdf",
        len(PDF),
    )
    assert (stored.checksum_sha256, stored.storage_uri, stored.created_at) == (
        hashlib.sha256(PDF).hexdigest(),
        _uri(PDF),
        NOW,
    )
    assert world.store.events == [f"store {_uri(PDF)}", "save", "commit"]


async def test_upload_validation_happens_before_storage(world: World) -> None:
    with pytest.raises(UnsupportedDocumentTypeError):
        await world.upload(mime="text/html")
    with pytest.raises(DocumentTooLargeError):
        await world.upload(content=b"x" * 257)
    with pytest.raises(DocumentTooLargeError):
        await world.upload(content=b"")
    with pytest.raises(ThemeNotFoundError):
        await world.upload(theme_id=uuid4())
    assert world.store.documentation_storage.blobs == {}


async def test_list_by_theme(world: World) -> None:
    first = await world.upload(b"one", "one.pdf")
    second = await world.upload(b"two", "two.docx", DOCX)
    c = world.container
    listed = await c.run(c.build_list_documentation, ListDocumentationQuery(world.theme_id))
    assert [(d.id, d.filename) for d in listed] == [(first, "one.pdf"), (second, "two.docx")]
    with pytest.raises(ThemeNotFoundError):
        await c.run(c.build_list_documentation, ListDocumentationQuery(uuid4()))


async def test_delete_removes_the_reference_then_the_blob(world: World) -> None:
    doc_id = await world.upload()
    world.store.events.clear()
    c = world.container

    await c.run(c.build_delete_documentation, DeleteDocumentationCommand(world.theme_id, doc_id))

    assert world.store.events == ["save", "commit", f"delete {_uri(PDF)}"]
    assert world.store.documentation.rows == {}
    with pytest.raises(DocumentationNotFoundError):
        await c.run(
            c.build_delete_documentation, DeleteDocumentationCommand(world.theme_id, doc_id)
        )


async def test_a_shared_blob_is_kept_while_still_referenced(world: World) -> None:
    other_theme = Theme.create(protocol_id=uuid4(), name="Nutrition")
    world.store.themes.rows[other_theme.id] = other_theme
    doc_id = await world.upload()
    await world.upload(theme_id=other_theme.id)  # same bytes, same blob
    c = world.container

    await c.run(c.build_delete_documentation, DeleteDocumentationCommand(world.theme_id, doc_id))

    assert _uri(PDF) in world.store.documentation_storage.blobs


async def test_delete_requires_the_document_to_belong_to_the_theme(world: World) -> None:
    doc_id = await world.upload()
    c = world.container
    with pytest.raises(DocumentationNotFoundError):
        await c.run(c.build_delete_documentation, DeleteDocumentationCommand(uuid4(), doc_id))
    assert doc_id in world.store.documentation.rows


async def test_download_url(world: World) -> None:
    doc_id = await world.upload()
    c = world.container
    result = await c.run(
        c.build_get_documentation_download_url, GetDocumentationDownloadUrlQuery(doc_id)
    )
    assert result.url.endswith("?ttl=600")
    assert result.expires_at == NOW + timedelta(seconds=600)
    with pytest.raises(DocumentationNotFoundError):
        await c.run(
            c.build_get_documentation_download_url, GetDocumentationDownloadUrlQuery(uuid4())
        )
