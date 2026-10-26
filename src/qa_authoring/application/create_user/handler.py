from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.access_response import AccessReferences, UserResult
from qa_authoring.application.user_errors import EmailAlreadyExistsError
from qa_authoring.domain.model.user import User

if TYPE_CHECKING:
    from qa_authoring.application.create_user.command import CreateUserCommand
    from qa_authoring.application.ports.user_repository import UserRepository


class CreateUserHandler:
    """Provision a user (active, no roles). Users are only ever created by an administrator."""

    def __init__(self, users: UserRepository) -> None:
        self._users = users

    async def __call__(self, command: CreateUserCommand) -> UserResult:
        user = User.create(email=command.email, display_name=command.display_name)
        if await self._users.find_by_email(user.email) is not None:
            raise EmailAlreadyExistsError(user.email)
        await self._users.add(user)
        return UserResult.of(user, AccessReferences({}, {}, {}))
