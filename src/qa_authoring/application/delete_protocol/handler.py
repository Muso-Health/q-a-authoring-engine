from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.protocol_errors import ProtocolHasThemesError, ProtocolNotFoundError

if TYPE_CHECKING:
    from qa_authoring.application.delete_protocol.command import DeleteProtocolCommand
    from qa_authoring.application.ports.protocol_repository import ProtocolRepository
    from qa_authoring.application.ports.theme_repository import ThemeRepository


class DeleteProtocolHandler:
    """Guarded delete: refused while themes still belong to the protocol."""

    def __init__(self, protocols: ProtocolRepository, themes: ThemeRepository) -> None:
        self._protocols = protocols
        self._themes = themes

    async def __call__(self, command: DeleteProtocolCommand) -> None:
        if await self._protocols.get(command.protocol_id) is None:
            raise ProtocolNotFoundError(command.protocol_id)
        if await self._themes.exists_for_protocol(command.protocol_id):
            raise ProtocolHasThemesError(command.protocol_id)
        await self._protocols.delete(command.protocol_id)
