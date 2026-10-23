from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.catalog_response import ThemeResult
from qa_authoring.application.protocol_errors import ProtocolNotFoundError

if TYPE_CHECKING:
    from qa_authoring.application.list_themes.command import ListThemesQuery
    from qa_authoring.application.ports.protocol_repository import ProtocolRepository
    from qa_authoring.application.ports.theme_repository import ThemeRepository


class ListThemesHandler:
    """The protocol's themes, ordered by name; the protocol must exist."""

    def __init__(self, themes: ThemeRepository, protocols: ProtocolRepository) -> None:
        self._themes = themes
        self._protocols = protocols

    async def __call__(self, query: ListThemesQuery) -> tuple[ThemeResult, ...]:
        if await self._protocols.get(query.protocol_id) is None:
            raise ProtocolNotFoundError(query.protocol_id)
        return tuple(
            ThemeResult.of(row) for row in await self._themes.list_by_protocol(query.protocol_id)
        )
