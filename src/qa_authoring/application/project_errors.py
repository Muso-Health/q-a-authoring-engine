from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID


class ProjectNotFoundError(Exception):
    def __init__(self, project_id: UUID) -> None:
        super().__init__(f"project {project_id} not found")
        self.project_id = project_id


class ProjectHasProtocolsError(Exception):
    def __init__(self, project_id: UUID) -> None:
        super().__init__(f"project {project_id} still has protocols")
        self.project_id = project_id


class UnknownBaseLanguageError(Exception):
    def __init__(self, language_id: UUID) -> None:
        super().__init__(f"base language {language_id} does not exist")
        self.language_id = language_id
