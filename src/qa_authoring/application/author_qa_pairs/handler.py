from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.author_qa_pairs.command import AuthoredPairsResult
from qa_authoring.application.qaset_errors import InvalidQAPairsError
from qa_authoring.application.theme_answers import qasets_by_answer
from qa_authoring.application.theme_errors import ThemeNotFoundError
from qa_authoring.domain.model.qaset import QASet

if TYPE_CHECKING:
    from uuid import UUID

    from qa_authoring.application.author_qa_pairs.command import AuthorQAPairsCommand
    from qa_authoring.application.ports.qaset_repository import QASetRepository
    from qa_authoring.application.ports.theme_repository import ThemeRepository
    from qa_authoring.application.validation_support import BaseLanguageResolver


class AuthorQAPairsHandler:
    """Author question-answer pairs under a theme, in its project's base language. Pairs are
    grouped by answer (trimmed, exact): one QA set per answer, each distinct question a variant.
    An answer the theme already has gains the new questions instead of a second QA set. The
    theme is locked for the transaction, so concurrent batches cannot both create one answer."""

    def __init__(
        self,
        qasets: QASetRepository,
        themes: ThemeRepository,
        base_language: BaseLanguageResolver,
    ) -> None:
        self._qasets = qasets
        self._themes = themes
        self._base_language = base_language

    async def __call__(self, command: AuthorQAPairsCommand) -> AuthoredPairsResult:
        invalid = tuple(
            i for i, p in enumerate(command.pairs) if not p.question.strip() or not p.answer.strip()
        )
        if invalid:
            raise InvalidQAPairsError(invalid)
        if await self._themes.get_for_update(command.theme_id) is None:
            raise ThemeNotFoundError(command.theme_id)
        language_id = await self._base_language.of_theme(command.theme_id)
        by_answer = await qasets_by_answer(self._qasets, command.theme_id, language_id)

        created: dict[str, QASet] = {}
        changed: dict[UUID, QASet] = {}
        taken = {
            answer: {v.text for v in qaset.presence(language_id).variants}
            for answer, qaset in by_answer.items()
        }
        skipped: list[int] = []
        added = 0
        for row, pair in enumerate(command.pairs):
            answer, question = pair.answer.strip(), pair.question.strip()
            qaset = by_answer.get(answer)
            if qaset is None:
                qaset = QASet.create(
                    theme_id=command.theme_id, language_id=language_id, answer_text=answer
                )
                by_answer[answer] = created[answer] = qaset
                taken[answer] = set()
            if question in taken[answer]:
                skipped.append(row)
                continue
            qaset.add_variant(language_id, question)
            taken[answer].add(question)
            added += 1
            if answer not in created:
                changed[qaset.id] = qaset

        for qaset in created.values():
            await self._qasets.add(qaset)
        for qaset in changed.values():
            await self._qasets.save(qaset)
        return AuthoredPairsResult(len(created), len(changed), added, tuple(skipped))
