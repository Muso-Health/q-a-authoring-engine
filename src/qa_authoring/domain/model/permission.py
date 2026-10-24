from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable


class Permission(StrEnum):
    """The fixed permission catalogue: the single source of truth, never stored as a table."""

    MANAGE_LANGUAGES = "manage_languages"
    MANAGE_CATALOG = "manage_catalog"
    AUTHOR_QASETS = "author_qasets"
    MANAGE_INTENTS = "manage_intents"
    MANAGE_CATEGORIES = "manage_categories"
    MANAGE_AUDIO = "manage_audio"
    VALIDATE_CLINICAL = "validate_clinical"
    VALIDATE_TRANSLATION = "validate_translation"
    VALIDATE_AUDIO = "validate_audio"
    MANAGE_ACCESS = "manage_access"
    MANAGE_PROMPTS = "manage_prompts"
    EXPORT_CORPUS = "export_corpus"


class UnknownPermissionError(ValueError):
    def __init__(self, codes: Iterable[str]) -> None:
        self.codes = tuple(sorted(set(codes)))
        super().__init__(f"unknown permission codes: {', '.join(map(repr, self.codes))}")


def parse_permissions(codes: Iterable[str]) -> frozenset[Permission]:
    codes = list(codes)
    known = {p.value for p in Permission}
    unknown = [code for code in codes if code not in known]
    if unknown:
        raise UnknownPermissionError(unknown)
    return frozenset(Permission(code) for code in codes)
