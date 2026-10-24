from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID


class NothingToExportError(Exception):
    """Raised when a project has no clinically validated QA set."""

    def __init__(self, project_id: UUID) -> None:
        super().__init__(f"project {project_id} has no clinically validated QA set to export")
        self.project_id = project_id
