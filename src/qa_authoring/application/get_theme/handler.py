from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.catalog_response import ThemeResult
from qa_authoring.application.theme_errors import ThemeNotFoundError

if TYPE_CHECKING:
    from qa_authoring.application.get_theme.command import GetThemeQuery
    from qa_authoring.application.ports.theme_repository import ThemeRepository


class GetThemeHandler:
    def __init__(self, themes: ThemeRepository) -> None:
        self._themes = themes

    async def __call__(self, query: GetThemeQuery) -> ThemeResult:
        theme = await self._themes.get(query.theme_id)
        if theme is None:
            raise ThemeNotFoundError(query.theme_id)
        return ThemeResult.of(theme)
