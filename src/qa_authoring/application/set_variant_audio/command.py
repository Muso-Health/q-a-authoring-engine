from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID  # noqa: TC003 — a field type on a frozen dataclass


@dataclass(frozen=True, slots=True)
class SetVariantAudioCommand:
    """``client_mime`` is what the browser claims; the probed type is authoritative."""

    qaset_id: UUID
    variant_id: UUID
    content: bytes
    client_mime: str | None
