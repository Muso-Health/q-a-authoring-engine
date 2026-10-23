from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.catalog_response import ProtocolResult
from qa_authoring.application.protocol_errors import ProtocolNotFoundError

if TYPE_CHECKING:
    from qa_authoring.application.get_protocol.command import GetProtocolQuery
    from qa_authoring.application.ports.protocol_repository import ProtocolRepository


class GetProtocolHandler:
    def __init__(self, protocols: ProtocolRepository) -> None:
        self._protocols = protocols

    async def __call__(self, query: GetProtocolQuery) -> ProtocolResult:
        protocol = await self._protocols.get(query.protocol_id)
        if protocol is None:
            raise ProtocolNotFoundError(query.protocol_id)
        return ProtocolResult.of(protocol)
