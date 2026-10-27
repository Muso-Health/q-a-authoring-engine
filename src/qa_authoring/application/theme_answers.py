from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.domain.model.qaset import LanguageNotPresentError

if TYPE_CHECKING:
    from uuid import UUID

    from qa_authoring.application.ports.qaset_repository import QASetRepository
    from qa_authoring.domain.model.qaset import QASet


async def qasets_by_answer(
    qasets: QASetRepository, theme_id: UUID, language_id: UUID
) -> dict[str, QASet]:
    """The theme's QA sets keyed by their answer in ``language_id`` (stored trimmed), for the
    one-answer-per-theme invariant. Callers lock the theme first."""
    found: dict[str, QASet] = {}
    for qaset in await qasets.list_by_theme(theme_id):
        try:
            answer = qaset.presence(language_id).answer.text
        except LanguageNotPresentError:
            continue
        found.setdefault(answer, qaset)
    return found
