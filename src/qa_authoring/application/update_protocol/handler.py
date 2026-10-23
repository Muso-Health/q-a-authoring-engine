from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.catalog_response import ProtocolResult
from qa_authoring.application.patch import apply_name_and_description
from qa_authoring.application.protocol_errors import ProtocolNotFoundError

if TYPE_CHECKING:
    from qa_authoring.application.ports.protocol_repository import ProtocolRepository
    from qa_authoring.application.update_protocol.command import UpdateProtocolCommand


class UpdateProtocolHandler:
    def __init__(self, protocols: ProtocolRepository) -> None:
        self._protocols = protocols

    async def __call__(self, command: UpdateProtocolCommand) -> ProtocolResult:
        protocol = await self._protocols.get(command.protocol_id)
        if protocol is None:
            raise ProtocolNotFoundError(command.protocol_id)
        apply_name_and_description(protocol, name=command.name, description=command.description)
        await self._protocols.update(protocol)
        return ProtocolResult.of(protocol)
