from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

    from qa_authoring.application.ports.translator import TranslatorPort


class TranslationEngine(StrEnum):
    LLM = "llm"
    GOOGLE = "google"


class UnknownEngineError(Exception):
    def __init__(self, engine: str) -> None:
        super().__init__(f"unknown or unavailable translation engine {engine!r}")
        self.engine = engine


class Translators:
    """The translation engines available to a request, chosen by key."""

    def __init__(self, engines: Mapping[TranslationEngine, TranslatorPort]) -> None:
        self._engines = dict(engines)

    def get(self, engine: str) -> TranslatorPort:
        try:
            return self._engines[TranslationEngine(engine)]
        except (ValueError, KeyError) as exc:
            raise UnknownEngineError(engine) from exc
