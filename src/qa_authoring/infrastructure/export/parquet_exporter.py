from __future__ import annotations

import asyncio
import io
from dataclasses import fields
from typing import TYPE_CHECKING, Any
from uuid import UUID

import pyarrow as pa
import pyarrow.parquet as pq

from qa_authoring.application.corpus_datasets import QaRow, TranslationLinkRow
from qa_authoring.application.ports.corpus_export import CorpusArtifacts

if TYPE_CHECKING:
    from collections.abc import Sequence

    from qa_authoring.application.corpus_datasets import CorpusDatasets
    from qa_authoring.application.ports.export_storage import ExportStoragePort

PARQUET_MIME_TYPE = "application/vnd.apache.parquet"

_TEXT, _TEXTS = pa.string(), pa.list_(pa.string())

QA_ROWS_SCHEMA = pa.schema(
    [
        pa.field("project_id", _TEXT, nullable=False),
        pa.field("project_name", _TEXT, nullable=False),
        pa.field("base_language_code", _TEXT, nullable=False),
        pa.field("protocol_id", _TEXT, nullable=False),
        pa.field("protocol_name", _TEXT, nullable=False),
        pa.field("theme_id", _TEXT, nullable=False),
        pa.field("theme_name", _TEXT, nullable=False),
        pa.field("qaset_id", _TEXT, nullable=False),
        pa.field("category_names", _TEXTS, nullable=False),
        pa.field("language_code", _TEXT, nullable=False),
        pa.field("question_variant_id", _TEXT, nullable=False),
        pa.field("question_text", _TEXT, nullable=False),
        pa.field("answer_id", _TEXT, nullable=False),
        pa.field("answer_text", _TEXT, nullable=False),
        pa.field("intents", _TEXTS, nullable=False),
        pa.field("variant_audio_uri", _TEXT),
        pa.field("answer_audio_uri", _TEXT),
        pa.field("clinical_validation_state", _TEXT, nullable=False),
        pa.field("translation_validation_state", _TEXT),
        pa.field("variant_audio_validation_state", _TEXT),
        pa.field("answer_audio_validation_state", _TEXT),
    ]
)

TRANSLATION_LINKS_SCHEMA = pa.schema(
    [
        pa.field("role", _TEXT, nullable=False),
        pa.field("item_a_id", _TEXT, nullable=False),
        pa.field("item_b_id", _TEXT, nullable=False),
        pa.field("qaset_id", _TEXT, nullable=False),
        pa.field("language_a_code", _TEXT, nullable=False),
        pa.field("language_b_code", _TEXT, nullable=False),
    ]
)


class ParquetCorpusExporter:
    """Writes each dataset to its own Parquet file (ids as strings, lists as list<string>) and
    stores it in the export storage."""

    def __init__(self, storage: ExportStoragePort) -> None:
        self._storage = storage

    async def export(self, datasets: CorpusDatasets) -> CorpusArtifacts:
        qa_rows = await self._write(datasets.qa_rows, QaRow, QA_ROWS_SCHEMA)
        links = await self._write(
            datasets.translation_links, TranslationLinkRow, TRANSLATION_LINKS_SCHEMA
        )
        return CorpusArtifacts(qa_rows=qa_rows, translation_links=links)

    async def _write(self, rows: Sequence[Any], row_type: type, schema: pa.Schema) -> str:
        content = await asyncio.to_thread(_parquet, rows, row_type, schema)
        return await self._storage.store(content, PARQUET_MIME_TYPE)


def _parquet(rows: Sequence[Any], row_type: type, schema: pa.Schema) -> bytes:
    columns = {f.name: [_value(getattr(row, f.name)) for row in rows] for f in fields(row_type)}
    buffer = io.BytesIO()
    pq.write_table(pa.Table.from_pydict(columns, schema=schema), buffer)
    return buffer.getvalue()


def _value(value: object) -> object:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, tuple):
        return list(value)
    return value
