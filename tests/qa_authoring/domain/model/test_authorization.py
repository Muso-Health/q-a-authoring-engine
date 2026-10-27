from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from qa_authoring.domain.model.authorization import Authorization, Grant
from qa_authoring.domain.model.permission import Permission, PermissionScope
from qa_authoring.domain.model.role import Role
from qa_authoring.domain.model.user import RoleAssignment, User

if TYPE_CHECKING:
    from uuid import UUID

P1, P2, FR, BM = uuid4(), uuid4(), uuid4(), uuid4()


def _authorization(*grants: tuple[list[Permission], UUID | None, UUID | None]) -> Authorization:
    """One role per (permissions, project, language) assignment."""
    user = User.create(email="u@example.org", display_name="U")
    roles: dict[UUID, Role] = {}
    for permissions, project_id, language_id in grants:
        role = Role.create(name=f"r{len(roles)}", permissions=permissions)
        roles[role.id] = role
        user.assign(role.id, project_id=project_id, language_id=language_id)
    return Authorization.of(user, roles)


def test_every_permission_has_a_scope_class() -> None:
    assert {p for p in Permission if p.scope is PermissionScope.GLOBAL} == {
        Permission.MANAGE_ACCESS,
        Permission.MANAGE_PROMPTS,
        Permission.MANAGE_LANGUAGES,
        Permission.MANAGE_INTENTS,
        Permission.MANAGE_CATEGORIES,
        Permission.MANAGE_GLOSSARY,
        Permission.MANAGE_CATALOG,
    }
    assert {p for p in Permission if p.scope is PermissionScope.PROJECT} == {
        Permission.AUTHOR_QASETS,
        Permission.VALIDATE_CLINICAL,
        Permission.EXPORT_CORPUS,
    }
    assert {p for p in Permission if p.scope is PermissionScope.PROJECT_LANGUAGE} == {
        Permission.VALIDATE_TRANSLATION,
        Permission.VALIDATE_AUDIO,
        Permission.MANAGE_AUDIO,
    }


def test_a_global_permission_ignores_the_scope_of_its_assignment() -> None:
    auth = _authorization(([Permission.MANAGE_CATALOG], P1, FR))
    assert auth.authorize(Permission.MANAGE_CATALOG)
    assert auth.authorize(Permission.MANAGE_CATALOG, P2, BM)


def test_a_wildcard_assignment_covers_every_project_and_language() -> None:
    auth = _authorization(([Permission.AUTHOR_QASETS, Permission.VALIDATE_TRANSLATION], None, None))
    assert auth.authorize(Permission.AUTHOR_QASETS, P1)
    assert auth.authorize(Permission.AUTHOR_QASETS, P2)
    assert auth.authorize(Permission.VALIDATE_TRANSLATION, P2, BM)


@pytest.mark.parametrize(
    "permission", [Permission.AUTHOR_QASETS, Permission.VALIDATE_CLINICAL, Permission.EXPORT_CORPUS]
)
def test_a_project_grant_covers_its_project_only(permission: Permission) -> None:
    auth = _authorization(([permission], P1, None))
    assert auth.authorize(permission, P1)
    assert not auth.authorize(permission, P2)
    assert not auth.authorize(permission)


def test_a_language_scope_is_ignored_by_project_permissions() -> None:
    auth = _authorization(([Permission.AUTHOR_QASETS, Permission.VALIDATE_CLINICAL], P1, BM))
    assert auth.authorize(Permission.AUTHOR_QASETS, P1, FR)
    assert auth.authorize(Permission.VALIDATE_CLINICAL, P1, FR)
    assert not auth.authorize(Permission.AUTHOR_QASETS, P2, BM)


@pytest.mark.parametrize("permission", [Permission.VALIDATE_TRANSLATION, Permission.VALIDATE_AUDIO])
def test_a_language_grant_covers_its_language_only(permission: Permission) -> None:
    auth = _authorization(([permission], P1, BM))
    assert auth.authorize(permission, P1, BM)
    assert not auth.authorize(permission, P1, FR)
    assert not auth.authorize(permission, P2, BM)


def test_a_project_only_grant_covers_every_language_of_its_project() -> None:
    auth = _authorization(([Permission.VALIDATE_TRANSLATION], P1, None))
    assert auth.authorize(Permission.VALIDATE_TRANSLATION, P1, BM)
    assert auth.authorize(Permission.VALIDATE_TRANSLATION, P1, FR)
    assert not auth.authorize(Permission.VALIDATE_TRANSLATION, P2, FR)


def test_a_language_only_grant_covers_that_language_in_every_project() -> None:
    auth = _authorization(([Permission.VALIDATE_AUDIO], None, BM))
    assert auth.authorize(Permission.VALIDATE_AUDIO, P1, BM)
    assert auth.authorize(Permission.VALIDATE_AUDIO, P2, BM)
    assert not auth.authorize(Permission.VALIDATE_AUDIO, P2, FR)


def test_effective_permissions_are_the_union_of_the_assignments() -> None:
    auth = _authorization(
        ([Permission.AUTHOR_QASETS], P1, None),
        ([Permission.VALIDATE_TRANSLATION], P2, BM),
        ([Permission.MANAGE_INTENTS], P2, BM),
    )
    assert auth.authorize(Permission.AUTHOR_QASETS, P1)
    assert auth.authorize(Permission.VALIDATE_TRANSLATION, P2, BM)
    assert not auth.authorize(Permission.VALIDATE_TRANSLATION, P1, BM)
    assert auth.permissions == frozenset(
        {Permission.AUTHOR_QASETS, Permission.VALIDATE_TRANSLATION, Permission.MANAGE_INTENTS}
    )
    assert auth.holds(Permission.AUTHOR_QASETS) and not auth.holds(Permission.MANAGE_ACCESS)
    # Normalized per scope class: a global grant carries no scope, a project one no language.
    assert set(auth.grants) == {
        Grant(Permission.AUTHOR_QASETS, P1),
        Grant(Permission.VALIDATE_TRANSLATION, P2, BM),
        Grant(Permission.MANAGE_INTENTS),
    }


def test_visibility_follows_the_projects_of_any_assignment() -> None:
    scoped = _authorization(([], P1, None), ([Permission.VALIDATE_AUDIO], P2, BM))
    assert scoped.visible_project_ids == frozenset({P1, P2})
    assert scoped.can_see(P1) and scoped.can_see(P2) and not scoped.can_see(uuid4())

    wildcard = _authorization(([Permission.MANAGE_LANGUAGES], None, None), ([], P1, None))
    assert wildcard.visible_project_ids is None
    assert wildcard.can_see(uuid4())

    assert _authorization().visible_project_ids == frozenset()


def test_an_inactive_user_holds_and_sees_nothing() -> None:
    user = User.create(email="u@example.org", display_name="U")
    role = Role.create(name="admin", permissions=list(Permission))
    user.assign(role.id)
    user.set_active(False)
    auth = Authorization.of(user, {role.id: role})
    assert auth.permissions == frozenset()
    assert not auth.authorize(Permission.MANAGE_ACCESS)
    assert auth.visible_project_ids == frozenset()


def test_assignments_are_unique_by_role_and_scope() -> None:
    user = User.create(email="u@example.org", display_name="U")
    role_id = uuid4()
    first, created = user.assign(role_id, project_id=P1)
    again, created_again = user.assign(role_id, project_id=P1)
    other, created_other = user.assign(role_id, project_id=P1, language_id=BM)
    assert (created, created_again, created_other) == (True, False, True)
    assert again == first and other != first
    assert isinstance(first, RoleAssignment)
    assert (first.role_id, first.project_id, first.language_id) == (role_id, P1, None)
    assert user.assignments == (first, other)
    assert user.role_ids == (role_id,)

    assert user.unassign(first.id) is True
    assert user.unassign(first.id) is False
    assert list(user.assignments) == [other]
