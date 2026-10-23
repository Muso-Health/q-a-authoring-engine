from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID


class ThemeNotFoundError(Exception):
    def __init__(self, theme_id: UUID) -> None:
        super().__init__(f"theme {theme_id} not found")
        self.theme_id = theme_id
