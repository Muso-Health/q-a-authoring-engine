from __future__ import annotations


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
