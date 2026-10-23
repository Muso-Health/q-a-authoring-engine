from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.catalog_response import ThemeResult
from qa_authoring.application.protocol_errors import ProtocolNotFoundError
from qa_authoring.domain.model.theme import Theme

if TYPE_CHECKING:
    from qa_authoring.application.create_theme.command import CreateThemeCommand
    from qa_authoring.application.ports.protocol_repository import ProtocolRepository
    from qa_authoring.application.ports.theme_repository import ThemeRepository


class CreateThemeHandler:
    def __init__(self, themes: ThemeRepository, protocols: ProtocolRepository) -> None:
        self._themes = themes
        self._protocols = protocols

    async def __call__(self, command: CreateThemeCommand) -> ThemeResult:
        if await self._protocols.get(command.protocol_id) is None:
            raise ProtocolNotFoundError(command.protocol_id)
        theme = Theme.create(
            protocol_id=command.protocol_id, name=command.name, description=command.description
        )
        await self._themes.add(theme)
        return ThemeResult.of(theme)
