from __future__ import annotations

import io
from uuid import uuid4

import pyarrow as pa
import pyarrow.parquet as pq

from qa_authoring.application.corpus_datasets import CorpusDatasets, QaRow, TranslationLinkRow
from qa_authoring.infrastructure.export.parquet_exporter import (
    PARQUET_MIME_TYPE,
    ParquetCorpusExporter,
)
from tests.fakes import InMemoryBlobStorage


def _row(**overrides: object) -> QaRow:
    values: dict[str, object] = {
        "project_id": uuid4(),
        "project_name": "Muso",
        "base_language_code": "fr",
        "protocol_id": uuid4(),
        "protocol_name": "Malaria protocol",
        "theme_id": uuid4(),
        "theme_name": "Fever",
        "qaset_id": uuid4(),
        "category_names": ("Fever", "Malaria"),
        "language_code": "bm",
        "question_variant_id": uuid4(),
        "question_text": "Mun min?",
        "answer_id": uuid4(),
        "answer_text": "Ji min.",
        "intents": ("Dosage",),
        "variant_audio_uri": "gs://bucket/audio/abc",
        "answer_audio_uri": None,
        "clinical_validation_state": "validated",
        "translation_validation_state": "pending",
        "variant_audio_validation_state": "rejected",
        "answer_audio_validation_state": None,
    }
    values.update(overrides)
    return QaRow(**values)  # type: ignore[arg-type]


def _read(storage: InMemoryBlobStorage, uri: str) -> pa.Table:
    return pq.read_table(io.BytesIO(storage.blobs[uri]))


async def test_round_trips_both_datasets_through_the_blob_storage() -> None:
    storage = InMemoryBlobStorage("exports")
    row = _row()
    bare = _row(category_names=(), intents=(), variant_audio_uri=None)
    link = TranslationLinkRow("variant", uuid4(), uuid4(), row.qaset_id, "bm", "fr")

    artifacts = await ParquetCorpusExporter(storage).export(CorpusDatasets((row, bare), (link,)))

    assert set(storage.blobs) == {artifacts.qa_rows, artifacts.translation_links}
    qa_rows = _read(storage, artifacts.qa_rows)
    assert qa_rows.column_names == list(QaRow.__dataclass_fields__)
    assert qa_rows.schema.field("category_names").type == pa.list_(pa.string())
    assert qa_rows.schema.field("intents").type == pa.list_(pa.string())
    assert qa_rows.schema.field("qaset_id").type == pa.string()
    assert not qa_rows.schema.field("question_text").nullable
    assert qa_rows.schema.field("answer_audio_uri").nullable
    first, second = qa_rows.to_pylist()
    assert first["category_names"] == ["Fever", "Malaria"]
    assert first["intents"] == ["Dosage"]
    assert first["qaset_id"] == str(row.qaset_id)
    assert first["answer_audio_uri"] is None
    assert first["variant_audio_uri"] == "gs://bucket/audio/abc"
    assert (second["category_names"], second["intents"]) == ([], [])

    links = _read(storage, artifacts.translation_links)
    assert links.column_names == [
        "role",
        "item_a_id",
        "item_b_id",
        "qaset_id",
        "language_a_code",
        "language_b_code",
    ]
    assert links.to_pylist() == [
        {
            "role": "variant",
            "item_a_id": str(link.item_a_id),
            "item_b_id": str(link.item_b_id),
            "qaset_id": str(link.qaset_id),
            "language_a_code": "bm",
            "language_b_code": "fr",
        }
    ]


async def test_empty_datasets_keep_their_schema() -> None:
    storage = InMemoryBlobStorage("exports")
    artifacts = await ParquetCorpusExporter(storage).export(CorpusDatasets((), ()))
    links = _read(storage, artifacts.translation_links)
    assert links.num_rows == 0 and links.column_names[0] == "role"
    assert _read(storage, artifacts.qa_rows).schema.field("intents").type == pa.list_(pa.string())


async def test_the_same_datasets_produce_the_same_files() -> None:
    storage = InMemoryBlobStorage("exports")
    datasets = CorpusDatasets((_row(),), ())
    first = await ParquetCorpusExporter(storage).export(datasets)
    second = await ParquetCorpusExporter(storage).export(datasets)
    assert first == second


async def test_stores_parquet_under_its_media_type() -> None:
    stored: list[str] = []

    class Recording(InMemoryBlobStorage):
        async def store(self, content: bytes, mime_type: str) -> str:
            stored.append(mime_type)
            return await super().store(content, mime_type)

    await ParquetCorpusExporter(Recording("exports")).export(CorpusDatasets((_row(),), ()))
    assert stored == [PARQUET_MIME_TYPE, PARQUET_MIME_TYPE]
    assert PARQUET_MIME_TYPE == "application/vnd.apache.parquet"
