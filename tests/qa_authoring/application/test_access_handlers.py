from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from qa_authoring.application.assign_role.command import AssignRoleCommand
from qa_authoring.application.bootstrap_admin.command import BootstrapAdminCommand
from qa_authoring.application.create_role.command import CreateRoleCommand
from qa_authoring.application.create_user.command import CreateUserCommand
from qa_authoring.application.delete_role.command import DeleteRoleCommand
from qa_authoring.application.get_role.command import GetRoleQuery
from qa_authoring.application.get_user.command import GetUserQuery
from qa_authoring.application.list_roles.command import ListRolesQuery
from qa_authoring.application.list_users.command import ListUsersQuery
from qa_authoring.application.ports.identity import Identity
from qa_authoring.application.resolve_current_user.command import ResolveCurrentUserQuery
from qa_authoring.application.role_errors import (
    RoleInUseError,
    RoleNameExistsError,
    RoleNotFoundError,
)
from qa_authoring.application.unassign_role.command import UnassignRoleCommand
from qa_authoring.application.update_role.command import UpdateRoleCommand
from qa_authoring.application.update_user.command import UpdateUserCommand
from qa_authoring.application.user_errors import (
    EmailAlreadyExistsError,
    NotProvisionedError,
    RoleNotAssignedError,
    UserNotFoundError,
)
from qa_authoring.domain.model.permission import Permission, UnknownPermissionError
from qa_authoring.domain.model.user import InvalidEmailError
from qa_authoring.domain.value_objects.naming import InvalidNameError
from tests.fakes import in_memory_container

if TYPE_CHECKING:
    from config.container import Container
    from qa_authoring.application.access_response import (
        CurrentUserResult,
        RoleResult,
        UserResult,
    )
    from tests.fakes import InMemoryStore


@pytest.fixture
def world() -> tuple[Container, InMemoryStore]:
    return in_memory_container()


async def _role(container: Container, name: str, *codes: str) -> RoleResult:
    return await container.run(container.build_create_role, CreateRoleCommand(name, codes))


async def _user(container: Container, email: str = "ada@example.org") -> UserResult:
    return await container.run(container.build_create_user, CreateUserCommand(email, "Ada"))


async def _assign(container: Container, user: UserResult, role: RoleResult) -> bool:
    _, created = await container.run(
        container.build_assign_role, AssignRoleCommand(user.id, role.id)
    )
    return created


# --- roles ---


async def test_create_list_get_role(world: tuple[Container, InMemoryStore]) -> None:
    container, _ = world
    role = await _role(container, " Author ", "author_qasets", "manage_audio")

    assert (role.name, role.permissions) == ("Author", ("author_qasets", "manage_audio"))
    assert await container.run(container.build_get_role, GetRoleQuery(role.id)) == role
    await _role(container, "Admin", *Permission)
    names = [r.name for r in await container.run(container.build_list_roles, ListRolesQuery())]
    assert names == ["Admin", "Author"]
    with pytest.raises(RoleNotFoundError):
        await container.run(container.build_get_role, GetRoleQuery(uuid4()))


async def test_role_validation(world: tuple[Container, InMemoryStore]) -> None:
    container, _ = world
    await _role(container, "Author", "author_qasets")
    with pytest.raises(RoleNameExistsError):
        await _role(container, "  AUTHOR ")
    with pytest.raises(UnknownPermissionError):
        await _role(container, "Pilot", "fly_planes")
    with pytest.raises(InvalidNameError):
        await _role(container, " ")


async def test_update_role(world: tuple[Container, InMemoryStore]) -> None:
    container, _ = world
    role = await _role(container, "Author", "author_qasets")
    await _role(container, "Admin")

    renamed = await container.run(
        container.build_update_role, UpdateRoleCommand(role.id, name="Senior author")
    )
    assert (renamed.name, renamed.permissions) == ("Senior author", ("author_qasets",))
    replaced = await container.run(
        container.build_update_role,
        UpdateRoleCommand(role.id, permission_codes=("manage_audio",)),
    )
    assert (replaced.name, replaced.permissions) == ("Senior author", ("manage_audio",))

    with pytest.raises(RoleNameExistsError):
        await container.run(container.build_update_role, UpdateRoleCommand(role.id, name="admin"))
    with pytest.raises(UnknownPermissionError):
        await container.run(
            container.build_update_role, UpdateRoleCommand(role.id, permission_codes=("x",))
        )
    with pytest.raises(RoleNotFoundError):
        await container.run(container.build_update_role, UpdateRoleCommand(uuid4(), name="x"))


async def test_delete_role_is_guarded_while_assigned(
    world: tuple[Container, InMemoryStore],
) -> None:
    container, store = world
    role = await _role(container, "Author", "author_qasets")
    user = await _user(container)
    await _assign(container, user, role)

    with pytest.raises(RoleInUseError):
        await container.run(container.build_delete_role, DeleteRoleCommand(role.id))
    assert role.id in store.roles.rows

    await container.run(container.build_unassign_role, UnassignRoleCommand(user.id, role.id))
    await container.run(container.build_delete_role, DeleteRoleCommand(role.id))
    assert role.id not in store.roles.rows
    with pytest.raises(RoleNotFoundError):
        await container.run(container.build_delete_role, DeleteRoleCommand(role.id))


# --- users ---


async def test_create_list_get_user(world: tuple[Container, InMemoryStore]) -> None:
    container, _ = world
    user = await container.run(
        container.build_create_user, CreateUserCommand(" Ada@Example.org ", " Ada Lovelace ")
    )

    assert (user.email, user.display_name, user.is_active, user.roles) == (
        "ada@example.org",
        "Ada Lovelace",
        True,
        (),
    )
    assert await container.run(container.build_get_user, GetUserQuery(user.id)) == user
    await _user(container, "babbage@example.org")
    emails = [u.email for u in await container.run(container.build_list_users, ListUsersQuery())]
    assert emails == ["ada@example.org", "babbage@example.org"]
    with pytest.raises(UserNotFoundError):
        await container.run(container.build_get_user, GetUserQuery(uuid4()))


async def test_user_validation(world: tuple[Container, InMemoryStore]) -> None:
    container, _ = world
    await _user(container, "ada@example.org")
    with pytest.raises(EmailAlreadyExistsError):
        await _user(container, "ADA@example.org")
    with pytest.raises(InvalidEmailError):
        await _user(container, "not-an-email")
    with pytest.raises(InvalidNameError):
        await container.run(container.build_create_user, CreateUserCommand("b@example.org", " "))


async def test_update_user(world: tuple[Container, InMemoryStore]) -> None:
    container, _ = world
    user = await _user(container)

    renamed = await container.run(
        container.build_update_user, UpdateUserCommand(user.id, display_name="Countess")
    )
    deactivated = await container.run(
        container.build_update_user, UpdateUserCommand(user.id, is_active=False)
    )

    assert (renamed.display_name, renamed.is_active) == ("Countess", True)
    assert (deactivated.display_name, deactivated.is_active) == ("Countess", False)
    with pytest.raises(UserNotFoundError):
        await container.run(container.build_update_user, UpdateUserCommand(uuid4(), is_active=True))


async def test_assign_and_unassign_roles(world: tuple[Container, InMemoryStore]) -> None:
    container, _ = world
    user = await _user(container)
    author, recorder = await _role(container, "Author"), await _role(container, "Recorder")

    assert await _assign(container, user, author) is True
    assert await _assign(container, user, recorder) is True
    assert await _assign(container, user, author) is False
    loaded = await container.run(container.build_get_user, GetUserQuery(user.id))
    assert [(r.id, r.name) for r in loaded.roles] == [
        (author.id, "Author"),
        (recorder.id, "Recorder"),
    ]

    after = await container.run(
        container.build_unassign_role, UnassignRoleCommand(user.id, author.id)
    )
    assert [r.name for r in after.roles] == ["Recorder"]
    with pytest.raises(RoleNotAssignedError):
        await container.run(container.build_unassign_role, UnassignRoleCommand(user.id, author.id))
    with pytest.raises(RoleNotFoundError):
        await container.run(container.build_assign_role, AssignRoleCommand(user.id, uuid4()))
    with pytest.raises(UserNotFoundError):
        await container.run(container.build_assign_role, AssignRoleCommand(uuid4(), author.id))


# --- current user ---


async def _resolve(
    container: Container, email: str, subject: str | None = None
) -> CurrentUserResult:
    return await container.run(
        container.build_resolve_current_user, ResolveCurrentUserQuery(Identity(email, subject))
    )


async def test_resolve_current_user_by_email_with_effective_permissions(
    world: tuple[Container, InMemoryStore],
) -> None:
    container, _ = world
    user = await _user(container)
    for role in (
        await _role(container, "Author", "author_qasets"),
        await _role(container, "Recorder", "manage_audio", "author_qasets"),
    ):
        await _assign(container, user, role)

    current = await container.run(
        container.build_resolve_current_user,
        ResolveCurrentUserQuery(Identity("ADA@example.org", None)),
    )

    assert (current.id, current.email, current.display_name) == (user.id, user.email, "Ada")
    assert current.permissions == ("author_qasets", "manage_audio")


async def test_unknown_or_inactive_users_are_not_provisioned(
    world: tuple[Container, InMemoryStore],
) -> None:
    container, _ = world
    with pytest.raises(NotProvisionedError):
        await _resolve(container, "stranger@example.org")
    user = await _user(container)
    await container.run(container.build_update_user, UpdateUserCommand(user.id, is_active=False))
    with pytest.raises(NotProvisionedError):
        await _resolve(container, "ada@example.org")


async def test_subject_is_backfilled_on_first_request_then_enforced(
    world: tuple[Container, InMemoryStore],
) -> None:
    container, store = world
    user = await _user(container)

    await _resolve(container, "ada@example.org", "accounts.google.com:1")
    assert store.users.rows[user.id].subject == "accounts.google.com:1"
    await _resolve(container, "ada@example.org", "accounts.google.com:1")
    await _resolve(container, "ada@example.org", None)
    with pytest.raises(NotProvisionedError):
        await _resolve(container, "ada@example.org", "accounts.google.com:2")


# --- bootstrap ---


async def test_bootstrap_admin_is_idempotent(world: tuple[Container, InMemoryStore]) -> None:
    container, store = world

    await container.run(container.build_bootstrap_admin, BootstrapAdminCommand("Root@Example.org"))
    snapshot = (
        {i: (r.name, r.permissions) for i, r in store.roles.rows.items()},
        {i: (u.email, u.is_active, u.role_ids) for i, u in store.users.rows.items()},
    )
    await container.run(container.build_bootstrap_admin, BootstrapAdminCommand("root@example.org"))

    assert (
        {i: (r.name, r.permissions) for i, r in store.roles.rows.items()},
        {i: (u.email, u.is_active, u.role_ids) for i, u in store.users.rows.items()},
    ) == snapshot
    [admin] = store.roles.rows.values()
    [root] = store.users.rows.values()
    assert (admin.name, admin.permissions) == ("admin", frozenset(Permission))
    assert (root.email, root.is_active, root.role_ids) == ("root@example.org", True, (admin.id,))
    current = await _resolve(container, "root@example.org")
    assert current.permissions == tuple(sorted(p.value for p in Permission))


async def test_bootstrap_repairs_an_existing_admin(world: tuple[Container, InMemoryStore]) -> None:
    container, store = world
    admin = await _role(container, "Admin", "manage_access")
    user = await _user(container, "root@example.org")
    await container.run(container.build_update_user, UpdateUserCommand(user.id, is_active=False))

    await container.run(container.build_bootstrap_admin, BootstrapAdminCommand("root@example.org"))

    assert store.roles.rows[admin.id].permissions == frozenset(Permission)
    repaired = store.users.rows[user.id]
    assert (repaired.is_active, repaired.role_ids) == (True, (admin.id,))
    assert len(store.roles.rows) == 1
