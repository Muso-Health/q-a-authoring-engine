from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from qa_authoring.domain.value_objects.naming import clean_name

if TYPE_CHECKING:
    from collections.abc import Iterable

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


@dataclass(frozen=True, slots=True)
class RoleAssignment:
    """A role held within a scope; a null project or language means any."""

    role_id: UUID
    project_id: UUID | None = None
    language_id: UUID | None = None
    id: UUID = field(default_factory=uuid4)

    @property
    def scope(self) -> tuple[UUID, UUID | None, UUID | None]:
        return (self.role_id, self.project_id, self.language_id)


class User:
    """A provisioned person, identified by email (case-insensitive). ``subject`` is the identity
    provider's stable id, bound on first sign-in. Only active users are authorized."""

    __slots__ = ("_assignments", "_display_name", "_email", "_id", "_is_active", "_subject")

    def __init__(
        self,
        user_id: UUID,
        email: str,
        display_name: str,
        *,
        subject: str | None = None,
        is_active: bool = True,
        assignments: Iterable[RoleAssignment] = (),
    ) -> None:
        self._id = user_id
        self._email = normalize_email(email)
        self._display_name = clean_name(display_name, subject="user")
        self._subject = subject
        self._is_active = is_active
        self._assignments = list(assignments)

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
    def assignments(self) -> tuple[RoleAssignment, ...]:
        return tuple(self._assignments)

    @property
    def role_ids(self) -> tuple[UUID, ...]:
        return tuple(dict.fromkeys(a.role_id for a in self._assignments))

    def rename(self, display_name: str) -> None:
        self._display_name = clean_name(display_name, subject="user")

    def set_active(self, is_active: bool) -> None:
        self._is_active = is_active

    def assign(
        self, role_id: UUID, *, project_id: UUID | None = None, language_id: UUID | None = None
    ) -> tuple[RoleAssignment, bool]:
        """Idempotent per (role, project, language): the flag says whether it was just added."""
        wanted = RoleAssignment(role_id, project_id, language_id)
        existing = next((a for a in self._assignments if a.scope == wanted.scope), None)
        if existing is not None:
            return existing, False
        self._assignments.append(wanted)
        return wanted, True

    def unassign(self, assignment_id: UUID) -> bool:
        kept = [a for a in self._assignments if a.id != assignment_id]
        removed = len(kept) != len(self._assignments)
        self._assignments = kept
        return removed

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
