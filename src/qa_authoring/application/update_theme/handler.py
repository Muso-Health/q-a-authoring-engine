from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.catalog_response import ThemeResult
from qa_authoring.application.patch import apply_name_and_description
from qa_authoring.application.theme_errors import ThemeNotFoundError

if TYPE_CHECKING:
    from qa_authoring.application.ports.theme_repository import ThemeRepository
    from qa_authoring.application.update_theme.command import UpdateThemeCommand


class UpdateThemeHandler:
    def __init__(self, themes: ThemeRepository) -> None:
        self._themes = themes

    async def __call__(self, command: UpdateThemeCommand) -> ThemeResult:
        theme = await self._themes.get(command.theme_id)
        if theme is None:
            raise ThemeNotFoundError(command.theme_id)
        apply_name_and_description(theme, name=command.name, description=command.description)
        await self._themes.update(theme)
        return ThemeResult.of(theme)
