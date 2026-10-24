from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from qa_authoring.domain.value_objects.naming import clean_name, normalize_key

if TYPE_CHECKING:
    from collections.abc import Iterable

    from qa_authoring.domain.model.permission import Permission


class Role:
    """A named set of permissions; unique by its normalized name."""

    __slots__ = ("_id", "_name", "_permissions")

    def __init__(self, role_id: UUID, name: str, permissions: Iterable[Permission]) -> None:
        self._id = role_id
        self._name = clean_name(name, subject="role")
        self._permissions = frozenset(permissions)

    @classmethod
    def create(cls, *, name: str, permissions: Iterable[Permission]) -> Role:
        return cls(uuid4(), name, permissions)

    @property
    def id(self) -> UUID:
        return self._id

    @property
    def name(self) -> str:
        return self._name

    @property
    def key(self) -> str:
        return normalize_key(self._name)

    @property
    def permissions(self) -> frozenset[Permission]:
        return self._permissions

    def rename(self, name: str) -> None:
        self._name = clean_name(name, subject="role")

    def replace_permissions(self, permissions: Iterable[Permission]) -> None:
        self._permissions = frozenset(permissions)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Role) and other._id == self._id

    def __hash__(self) -> int:
        return hash(self._id)

    def __repr__(self) -> str:
        return f"Role(id={self._id}, name={self._name!r})"
