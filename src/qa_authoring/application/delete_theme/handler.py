from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.theme_errors import ThemeNotFoundError

if TYPE_CHECKING:
    from qa_authoring.application.delete_theme.command import DeleteThemeCommand
    from qa_authoring.application.ports.theme_repository import ThemeRepository


class DeleteThemeHandler:
    def __init__(self, themes: ThemeRepository) -> None:
        self._themes = themes

    async def __call__(self, command: DeleteThemeCommand) -> None:
        if await self._themes.get(command.theme_id) is None:
            raise ThemeNotFoundError(command.theme_id)
        await self._themes.delete(command.theme_id)
