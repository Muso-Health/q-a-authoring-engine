from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Final, Literal

if TYPE_CHECKING:
    from qa_authoring.domain.model._named_entity import NamedEntity


class _Unchanged(Enum):
    UNCHANGED = "unchanged"


UNCHANGED: Final = _Unchanged.UNCHANGED
type Unchanged = Literal[_Unchanged.UNCHANGED]


def apply_name_and_description(
    entity: NamedEntity, *, name: str | None, description: str | Unchanged | None
) -> None:
    """Partial update: ``name=None`` keeps the name; ``description`` is cleared by ``None`` and
    kept by ``UNCHANGED``."""
    if name is not None:
        entity.rename(name)
    if description is not UNCHANGED:
        entity.describe(description)
