from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.validation_response import ValidationResult
from qa_authoring.domain.model.validation import Validation, parse_decision

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime
    from uuid import UUID

    from qa_authoring.application.ports.project_repository import ProjectRepository
    from qa_authoring.application.ports.protocol_repository import ProtocolRepository
    from qa_authoring.application.ports.theme_repository import ThemeRepository
    from qa_authoring.application.ports.user_repository import UserRepository
    from qa_authoring.application.ports.validation_repository import ValidationRepository
    from qa_authoring.domain.model.qaset import QASet
    from qa_authoring.domain.model.validation import ValidationKind, ValidationSubject


class BaseLanguageResolver:
    """The base language of a QA set's project: QA set -> theme -> protocol -> project. The
    chain is held by RESTRICT foreign keys, so every link exists."""

    def __init__(
        self, themes: ThemeRepository, protocols: ProtocolRepository, projects: ProjectRepository
    ) -> None:
        self._themes = themes
        self._protocols = protocols
        self._projects = projects

    async def of(self, qaset: QASet) -> UUID:
        return await self.of_theme(qaset.theme_id)

    async def of_theme(self, theme_id: UUID) -> UUID:
        theme = await self._themes.get(theme_id)
        assert theme is not None
        protocol = await self._protocols.get(theme.protocol_id)
        assert protocol is not None
        project = await self._projects.get(protocol.project_id)
        assert project is not None
        return project.base_language_id


class DecisionRecorder:
    """Records a decision on a subject: the first one creates its Validation, later ones append
    to its history. Answers with the subject's full history, actors shown by email."""

    def __init__(
        self,
        validations: ValidationRepository,
        users: UserRepository,
        clock: Callable[[], datetime],
    ) -> None:
        self._validations = validations
        self._users = users
        self._clock = clock

    async def record(
        self,
        subject: ValidationSubject,
        decision: str,
        *,
        actor_user_id: UUID,
        note: str | None,
    ) -> tuple[ValidationResult, bool]:
        state = parse_decision(decision)
        validation = await self._validations.get_for(subject)
        if validation is None:
            validation = Validation.start(
                subject, state, actor_user_id=actor_user_id, at=self._clock(), note=note
            )
            await self._validations.add(validation)
            created = True
        else:
            validation.decide(state, actor_user_id=actor_user_id, at=self._clock(), note=note)
            await self._validations.save(validation)
            created = False
        return await self.describe(subject.kind, validation), created

    async def describe(
        self, kind: ValidationKind, validation: Validation | None
    ) -> ValidationResult:
        emails: dict[UUID, str] = {}
        for event in () if validation is None else validation.events:
            if event.actor_user_id not in emails:
                user = await self._users.get(event.actor_user_id)
                emails[event.actor_user_id] = "" if user is None else user.email
        return ValidationResult.of(kind, validation, emails)

    async def history(self, subject: ValidationSubject) -> ValidationResult:
        return await self.describe(subject.kind, await self._validations.get_for(subject))
