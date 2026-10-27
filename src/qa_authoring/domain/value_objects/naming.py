from __future__ import annotations

import unicodedata


class InvalidNameError(ValueError):
    """Raised when a name is blank."""


def clean_name(name: str, *, subject: str) -> str:
    cleaned = name.strip()
    if not cleaned:
        raise InvalidNameError(f"{subject} name must not be blank")
    return cleaned


def clean_description(description: str | None) -> str | None:
    """Trimmed; a blank description is no description."""
    if description is None:
        return None
    return description.strip() or None


class InvalidTextError(ValueError):
    """Raised when an answer or question text is blank."""


def clean_text(text: str, *, subject: str) -> str:
    cleaned = text.strip()
    if not cleaned:
        raise InvalidTextError(f"{subject} text must not be blank")
    return cleaned


def normalize_key(text: str) -> str:
    """A catalogue uniqueness key: trimmed, inner whitespace collapsed, lowercased."""
    return " ".join(text.split()).lower()


def search_fold(text: str) -> str:
    """A search key: accents dropped, casefolded, whitespace collapsed."""
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(stripped.casefold().split())
