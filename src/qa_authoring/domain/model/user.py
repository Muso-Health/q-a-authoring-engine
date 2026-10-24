from __future__ import annotations

import re
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from qa_authoring.domain.value_objects.naming import clean_name

if TYPE_CHECKING:
    from collections.abc import Iterable

    from qa_authoring.domain.model.permission import Permission
    from qa_authoring.domain.model.role import Role

_EMAIL = re.compile(r"[^@\s]+@[^@\s]+")


class InvalidEmailError(ValueError):
    def __init__(self, email: str) -> None:
        super().__init__(f"invalid email address {email!r}")
        self.email = email


class SubjectMismatchError(Exception):
    """Raised when an identity's subject differs from the one already bound to the user."""

    def __init__(self, user_id: UUID) -> None:
        super().__init__(f"user {user_id} is bound to another identity")
        self.user_id = user_id


def normalize_email(email: str) -> str:
    normalized = email.strip().lower()
    if not _EMAIL.fullmatch(normalized):
        raise InvalidEmailError(email)
    return normalized


class User:
    """A provisioned person, identified by email (case-insensitive). ``subject`` is the identity
    provider's stable id, bound on first sign-in. Only active users are authorized."""

    __slots__ = ("_display_name", "_email", "_id", "_is_active", "_role_ids", "_subject")

    def __init__(
        self,
        user_id: UUID,
        email: str,
        display_name: str,
        *,
        subject: str | None = None,
        is_active: bool = True,
        role_ids: Iterable[UUID] = (),
    ) -> None:
        self._id = user_id
        self._email = normalize_email(email)
        self._display_name = clean_name(display_name, subject="user")
        self._subject = subject
        self._is_active = is_active
        self._role_ids: dict[UUID, None] = dict.fromkeys(role_ids)

    @classmethod
    def create(cls, *, email: str, display_name: str) -> User:
        return cls(uuid4(), email, display_name)

    @property
    def id(self) -> UUID:
        return self._id

    @property
    def email(self) -> str:
        return self._email

    @property
    def display_name(self) -> str:
        return self._display_name

    @property
    def subject(self) -> str | None:
        return self._subject

    @property
    def is_active(self) -> bool:
        return self._is_active

    @property
    def role_ids(self) -> tuple[UUID, ...]:
        return tuple(self._role_ids)

    def rename(self, display_name: str) -> None:
        self._display_name = clean_name(display_name, subject="user")

    def set_active(self, is_active: bool) -> None:
        self._is_active = is_active

    def assign_role(self, role_id: UUID) -> bool:
        if role_id in self._role_ids:
            return False
        self._role_ids[role_id] = None
        return True

    def unassign_role(self, role_id: UUID) -> bool:
        if role_id not in self._role_ids:
            return False
        del self._role_ids[role_id]
        return True

    def bind_subject(self, subject: str) -> bool:
        """Bind the identity provider's subject on first sign-in; True if it was just bound."""
        if self._subject is None:
            self._subject = subject
            return True
        if self._subject != subject:
            raise SubjectMismatchError(self._id)
        return False

    def __eq__(self, other: object) -> bool:
        return isinstance(other, User) and other._id == self._id

    def __hash__(self) -> int:
        return hash(self._id)

    def __repr__(self) -> str:
        return f"User(id={self._id}, email={self._email!r})"


def effective_permissions(user: User, roles: Iterable[Role]) -> frozenset[Permission]:
    """The union of the permissions of the user's roles; none at all for an inactive user."""
    if not user.is_active:
        return frozenset()
    assigned = set(user.role_ids)
    return frozenset(p for role in roles if role.id in assigned for p in role.permissions)
