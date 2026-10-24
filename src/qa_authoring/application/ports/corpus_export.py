from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from qa_authoring.application.corpus_datasets import CorpusDatasets


@dataclass(frozen=True, slots=True)
class CorpusArtifacts:
    """The storage reference of each written dataset."""

    qa_rows: str
    translation_links: str


class ExportPort(Protocol):
    """Writes the corpus datasets to files in the export storage."""

    async def export(self, datasets: CorpusDatasets) -> CorpusArtifacts: ...
