from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable


class PermissionScope(StrEnum):
    """What an assignment's scope means for a permission: ignored (GLOBAL), its project only
    (PROJECT), or both its project and its language (PROJECT_LANGUAGE)."""

    GLOBAL = "global"
    PROJECT = "project"
    PROJECT_LANGUAGE = "project_language"


class Permission(StrEnum):
    """The fixed permission catalogue: the single source of truth, never stored as a table."""

    MANAGE_LANGUAGES = "manage_languages"
    MANAGE_CATALOG = "manage_catalog"
    AUTHOR_QASETS = "author_qasets"
    MANAGE_INTENTS = "manage_intents"
    MANAGE_CATEGORIES = "manage_categories"
    MANAGE_GLOSSARY = "manage_glossary"
    MANAGE_AUDIO = "manage_audio"
    VALIDATE_CLINICAL = "validate_clinical"
    VALIDATE_TRANSLATION = "validate_translation"
    VALIDATE_AUDIO = "validate_audio"
    MANAGE_ACCESS = "manage_access"
    MANAGE_PROMPTS = "manage_prompts"
    EXPORT_CORPUS = "export_corpus"

    @property
    def scope(self) -> PermissionScope:
        return _SCOPES[self]


# Explicit for every permission, so a new one cannot silently default to the widest class.
_SCOPES = {
    Permission.MANAGE_ACCESS: PermissionScope.GLOBAL,
    Permission.MANAGE_PROMPTS: PermissionScope.GLOBAL,
    Permission.MANAGE_LANGUAGES: PermissionScope.GLOBAL,
    Permission.MANAGE_INTENTS: PermissionScope.GLOBAL,
    Permission.MANAGE_CATEGORIES: PermissionScope.GLOBAL,
    Permission.MANAGE_GLOSSARY: PermissionScope.GLOBAL,
    Permission.MANAGE_CATALOG: PermissionScope.GLOBAL,
    Permission.AUTHOR_QASETS: PermissionScope.PROJECT,
    Permission.VALIDATE_CLINICAL: PermissionScope.PROJECT,
    Permission.EXPORT_CORPUS: PermissionScope.PROJECT,
    Permission.VALIDATE_TRANSLATION: PermissionScope.PROJECT_LANGUAGE,
    Permission.VALIDATE_AUDIO: PermissionScope.PROJECT_LANGUAGE,
    Permission.MANAGE_AUDIO: PermissionScope.PROJECT_LANGUAGE,
}


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
