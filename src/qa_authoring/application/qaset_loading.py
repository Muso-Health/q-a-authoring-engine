from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.qaset_errors import QASetNotFoundError

if TYPE_CHECKING:
    from uuid import UUID

    from qa_authoring.application.ports.qaset_repository import QASetRepository
    from qa_authoring.domain.model.qaset import QASet


async def load_qaset(qasets: QASetRepository, qaset_id: UUID) -> QASet:
    qaset = await qasets.get(qaset_id)
    if qaset is None:
        raise QASetNotFoundError(qaset_id)
    return qaset
