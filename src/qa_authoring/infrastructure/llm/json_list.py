from __future__ import annotations

import json
import re
from typing import Any

_FENCE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)


class ListParseError(ValueError):
    """The model's reply is not a usable JSON array of strings."""


def parse_string_list(reply: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    """The JSON array of strings in a model ``reply``: whitespace-normalized, without blanks or
    duplicates (ignoring case; the first spelling wins). A Markdown fence or prose around the
    array is tolerated; a reply that is JSON but not an array is not. An array that ends up empty
    is an error unless ``allow_empty``."""
    text = reply.strip()
    fenced = _FENCE.match(text)
    if fenced:
        text = fenced.group(1)
    parsed = _json_array(text)
    if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
        raise ListParseError("did not return a list of strings")
    items: dict[str, str] = {}
    for item in parsed:
        cleaned = " ".join(item.split())
        if cleaned:
            items.setdefault(cleaned.casefold(), cleaned)
    if not items and not allow_empty:
        raise ListParseError("returned an empty list")
    return tuple(items.values())


def _json_array(text: str) -> Any:
    try:
        return json.loads(text)
    except ValueError:
        start, end = text.find("["), text.rfind("]")
        if start == -1 or end <= start:
            raise ListParseError("did not return a list of strings") from None
        try:
            return json.loads(text[start : end + 1])
        except ValueError:
            raise ListParseError("did not return a list of strings") from None
