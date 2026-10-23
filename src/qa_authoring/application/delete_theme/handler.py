from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.theme_errors import ThemeHasQASetsError, ThemeNotFoundError

if TYPE_CHECKING:
    from qa_authoring.application.delete_theme.command import DeleteThemeCommand
    from qa_authoring.application.ports.qaset_repository import QASetRepository
    from qa_authoring.application.ports.theme_repository import ThemeRepository


class DeleteThemeHandler:
    """Guarded delete: refused while QA sets still belong to the theme."""

    def __init__(self, themes: ThemeRepository, qasets: QASetRepository) -> None:
        self._themes = themes
        self._qasets = qasets

    async def __call__(self, command: DeleteThemeCommand) -> None:
        if await self._themes.get(command.theme_id) is None:
            raise ThemeNotFoundError(command.theme_id)
        if await self._qasets.exists_for_theme(command.theme_id):
            raise ThemeHasQASetsError(command.theme_id)
        await self._themes.delete(command.theme_id)
