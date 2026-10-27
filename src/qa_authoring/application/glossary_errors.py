from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID


class GlossaryTermNotFoundError(Exception):
    def __init__(self, term_id: UUID) -> None:
        super().__init__(f"glossary term {term_id} not found")
        self.term_id = term_id
