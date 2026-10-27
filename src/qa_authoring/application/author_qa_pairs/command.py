from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID  # noqa: TC003 — a field type on a frozen dataclass

MAX_QA_PAIRS = 500


@dataclass(frozen=True, slots=True)
class QAPair:
    question: str
    answer: str


@dataclass(frozen=True, slots=True)
class AuthorQAPairsCommand:
    """Pairs authored in the theme's project base language; there is no language to give."""

    theme_id: UUID
    pairs: tuple[QAPair, ...]


@dataclass(frozen=True, slots=True)
class AuthoredPairsResult:
    """``skipped_rows``: indices of pairs whose question the answer already had."""

    qasets_created: int
    qasets_updated: int
    variants_added: int
    skipped_rows: tuple[int, ...]
