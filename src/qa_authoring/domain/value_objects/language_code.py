from __future__ import annotations

import re
from dataclasses import dataclass

_PATTERN = re.compile(r"[a-z]+(?:_[a-z]+)*")


class InvalidLanguageCodeError(ValueError):
    """Raised when a language code is not lowercase ASCII letters in ``_``-separated segments."""


@dataclass(frozen=True, slots=True)
class LanguageCode:
    """A language's natural key, e.g. ``fr``, ``bm`` or ``bm_fr``. Any well-formed code is
    accepted — the set of languages is data, not code."""

    value: str

    def __post_init__(self) -> None:
        if not _PATTERN.fullmatch(self.value):
            raise InvalidLanguageCodeError(
                f"invalid language code {self.value!r}: expected lowercase ASCII letters in "
                "one or more '_'-separated segments (e.g. 'fr', 'bm_fr')"
            )
