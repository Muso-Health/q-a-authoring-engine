from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID  # noqa: TC003 — a field type on frozen dataclasses


@dataclass(frozen=True, slots=True)
class QaRow:
    """One question variant of a clinically validated QA set, with its answer and context.
    Validation states are ``validated``/``rejected``/``pending``, or None where they do not
    apply: no audio, or a translation state for an item in the base language."""

    project_id: UUID
    project_name: str
    base_language_code: str
    protocol_id: UUID
    protocol_name: str
    theme_id: UUID
    theme_name: str
    qaset_id: UUID
    category_names: tuple[str, ...]
    language_code: str
    question_variant_id: UUID
    question_text: str
    answer_id: UUID
    answer_text: str
    intents: tuple[str, ...]
    variant_audio_uri: str | None
    answer_audio_uri: str | None
    clinical_validation_state: str
    translation_validation_state: str | None
    variant_audio_validation_state: str | None
    answer_audio_validation_state: str | None


@dataclass(frozen=True, slots=True)
class TranslationLinkRow:
    """One undirected translation link, in its canonical order (``item_a_id < item_b_id``)."""

    role: Literal["answer", "variant"]
    item_a_id: UUID
    item_b_id: UUID
    qaset_id: UUID
    language_a_code: str
    language_b_code: str


@dataclass(frozen=True, slots=True)
class CorpusDatasets:
    """The exported corpus: flat, ordered by ids so the same corpus exports identically. A
    language with an answer but no question variant contributes no ``qa_rows`` row."""

    qa_rows: tuple[QaRow, ...]
    translation_links: tuple[TranslationLinkRow, ...]
