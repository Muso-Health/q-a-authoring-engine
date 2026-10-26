from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.access_response import CurrentUserResult
from qa_authoring.application.user_errors import NotProvisionedError
from qa_authoring.domain.model.authorization import Authorization
from qa_authoring.domain.model.user import SubjectMismatchError

if TYPE_CHECKING:
    from qa_authoring.application.ports.role_repository import RoleRepository
    from qa_authoring.application.ports.user_repository import UserRepository
    from qa_authoring.application.resolve_current_user.command import ResolveCurrentUserQuery


class ResolveCurrentUserHandler:
    """Map an authenticated identity to its active user, by email. Users are never created here.
    The identity provider's subject is bound on first sign-in; a different subject later means a
    different person behind a reused email, and is refused."""

    def __init__(self, users: UserRepository, roles: RoleRepository) -> None:
        self._users = users
        self._roles = roles

    async def __call__(self, query: ResolveCurrentUserQuery) -> CurrentUserResult:
        identity = query.identity
        user = await self._users.find_by_email(identity.email)
        if user is None or not user.is_active:
            raise NotProvisionedError(identity.email)
        if identity.subject is not None:
            try:
                bound = user.bind_subject(identity.subject)
            except SubjectMismatchError as exc:
                raise NotProvisionedError(identity.email) from exc
            if bound:
                await self._users.update(user)
        roles = await self._roles.get_many(set(user.role_ids))
        return CurrentUserResult.of(user, Authorization.of(user, roles))
