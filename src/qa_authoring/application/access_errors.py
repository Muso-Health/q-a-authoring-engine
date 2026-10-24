from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from qa_authoring.domain.model.permission import Permission


class PermissionDeniedError(Exception):
    def __init__(self, permission: Permission) -> None:
        super().__init__(f"this action requires the {permission.value} permission")
        self.permission = permission
