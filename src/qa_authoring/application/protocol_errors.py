from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID


class ProtocolNotFoundError(Exception):
    def __init__(self, protocol_id: UUID) -> None:
        super().__init__(f"protocol {protocol_id} not found")
        self.protocol_id = protocol_id


class ProtocolHasThemesError(Exception):
    def __init__(self, protocol_id: UUID) -> None:
        super().__init__(f"protocol {protocol_id} still has themes")
        self.protocol_id = protocol_id
