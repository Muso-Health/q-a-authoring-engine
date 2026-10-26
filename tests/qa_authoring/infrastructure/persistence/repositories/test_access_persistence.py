from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from config.container import Container
from qa_authoring.application.bootstrap_admin.command import BootstrapAdminCommand
from qa_authoring.application.role_errors import RoleInUseError, RoleNameExistsError
from qa_authoring.application.user_errors import EmailAlreadyExistsError
from qa_authoring.domain.model.language import Language
from qa_authoring.domain.model.permission import Permission
from qa_authoring.domain.model.project import Project
from qa_authoring.domain.model.role import Role
from qa_authoring.domain.model.user import RoleAssignment, User
from qa_authoring.domain.value_objects.language_code import LanguageCode
from qa_authoring.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork
from tests.fakes import AUDIO_POLICY, FakeAudioProbe, InMemoryAudioStorage

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

pytestmark = pytest.mark.integration


async def test_users_roles_and_assignments_round_trip(migrated_engine: AsyncEngine) -> None:
    author = Role.create(name="Author", permissions=[Permission.AUTHOR_QASETS])
    admin = Role.create(name="Admin", permissions=list(Permission))
    user = User.create(email="Ada@Example.org", display_name="Ada")
    user.assign(author.id)
    user.assign(admin.id)
    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        await uow.roles.add(author)
        await uow.roles.add(admin)
        await uow.users.add(user)

    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        loaded = await uow.users.find_by_email(" ADA@example.ORG ")
        by_id = await uow.users.get(user.id)
        roles = await uow.roles.get_many({author.id, admin.id, uuid4()})
        listed = await uow.roles.list()
        found = await uow.roles.find_by_key("admin")
        assert await uow.users.uses_role(author.id)

    assert loaded is not None
    assert by_id is not None
    for candidate in (loaded, by_id):
        assert (candidate.id, candidate.email, candidate.display_name) == (
            user.id,
            "ada@example.org",
            "Ada",
        )
        assert (candidate.is_active, candidate.subject) == (True, None)
        assert candidate.role_ids == (author.id, admin.id)
    assert roles[admin.id].permissions == frozenset(Permission)
    assert [r.name for r in listed] == ["Admin", "Author"]
    assert found is not None
    assert found.id == admin.id


async def test_update_persists_every_change(migrated_engine: AsyncEngine) -> None:
    author = Role.create(name="Author", permissions=[Permission.AUTHOR_QASETS])
    recorder = Role.create(name="Recorder", permissions=[Permission.MANAGE_AUDIO])
    user = User.create(email="ada@example.org", display_name="Ada")
    [authored, _] = user.assign(author.id)
    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        await uow.roles.add(author)
        await uow.roles.add(recorder)
        await uow.users.add(user)

    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        loaded_user = await uow.users.get(user.id)
        loaded_role = await uow.roles.get(author.id)
        assert loaded_user is not None
        assert loaded_role is not None
        loaded_user.rename("Countess")
        loaded_user.set_active(False)
        loaded_user.bind_subject("accounts.google.com:1")
        loaded_user.unassign(authored.id)
        loaded_user.assign(recorder.id)
        loaded_role.rename("Writer")
        loaded_role.replace_permissions([Permission.MANAGE_INTENTS, Permission.AUTHOR_QASETS])
        await uow.users.update(loaded_user)
        await uow.roles.update(loaded_role)

    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        reloaded_user = await uow.users.get(user.id)
        reloaded_role = await uow.roles.get(author.id)
        assert not await uow.users.uses_role(author.id)
    assert reloaded_user is not None
    assert reloaded_role is not None
    assert (reloaded_user.display_name, reloaded_user.is_active, reloaded_user.subject) == (
        "Countess",
        False,
        "accounts.google.com:1",
    )
    assert reloaded_user.role_ids == (recorder.id,)
    assert (reloaded_role.name, reloaded_role.permissions) == (
        "Writer",
        frozenset({Permission.MANAGE_INTENTS, Permission.AUTHOR_QASETS}),
    )


async def test_unique_constraints(migrated_engine: AsyncEngine) -> None:
    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        await uow.users.add(User.create(email="ada@example.org", display_name="Ada"))
        await uow.roles.add(Role.create(name="Author", permissions=[]))

    with pytest.raises(EmailAlreadyExistsError):
        async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
            await uow.users.add(User.create(email="ADA@example.org", display_name="Other"))
    with pytest.raises(RoleNameExistsError):
        async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
            await uow.roles.add(Role.create(name=" author ", permissions=[]))

    insert = text(
        "INSERT INTO users (id, email, display_name, subject, is_active) "
        "VALUES (:id, :email, 'X', :subject, true)"
    )
    with pytest.raises(IntegrityError, match="uq_users_email_lower"):
        async with migrated_engine.begin() as connection:
            await connection.execute(
                insert, {"id": uuid4(), "email": "ADA@EXAMPLE.ORG", "subject": None}
            )
    async with migrated_engine.begin() as connection:
        await connection.execute(insert, {"id": uuid4(), "email": "b@example.org", "subject": "s1"})
        await connection.execute(insert, {"id": uuid4(), "email": "c@example.org", "subject": None})
    with pytest.raises(IntegrityError, match="uq_users_subject"):
        async with migrated_engine.begin() as connection:
            await connection.execute(
                insert, {"id": uuid4(), "email": "d@example.org", "subject": "s1"}
            )


async def test_assigned_role_delete_is_restricted(migrated_engine: AsyncEngine) -> None:
    role = Role.create(name="Author", permissions=[Permission.AUTHOR_QASETS])
    user = User.create(email="ada@example.org", display_name="Ada")
    [assignment, _] = user.assign(role.id)
    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        await uow.roles.add(role)
        await uow.users.add(user)

    with pytest.raises(RoleInUseError):
        async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
            await uow.roles.delete(role.id)

    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        assert await uow.roles.get(role.id) is not None
        loaded = await uow.users.get(user.id)
        assert loaded is not None
        loaded.unassign(assignment.id)
        await uow.users.update(loaded)
    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        await uow.roles.delete(role.id)
    async with migrated_engine.connect() as connection:
        remaining = await connection.scalar(text("SELECT count(*) FROM role_permissions"))
    assert remaining == 0


async def _scoped_world(engine: AsyncEngine) -> tuple[Role, User, Project, Language]:
    fr = Language.register(LanguageCode("fr"), "French")
    project = Project.create(name="Muso", base_language_id=fr.id)
    role = Role.create(name="Reviewer", permissions=[Permission.VALIDATE_TRANSLATION])
    user = User.create(email="ada@example.org", display_name="Ada")
    user.assign(role.id)
    user.assign(role.id, project_id=project.id)
    user.assign(role.id, project_id=project.id, language_id=fr.id)
    user.assign(role.id, language_id=fr.id)
    async with SqlAlchemyUnitOfWork(engine) as uow:
        await uow.languages.add(fr)
        await uow.projects.add(project)
        await uow.roles.add(role)
        await uow.users.add(user)
    return role, user, project, fr


async def test_scoped_assignments_round_trip(migrated_engine: AsyncEngine) -> None:
    _, user, _, _ = await _scoped_world(migrated_engine)
    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        loaded = await uow.users.get(user.id)
    assert loaded is not None
    assert loaded.assignments == user.assignments
    assert all(isinstance(a, RoleAssignment) for a in loaded.assignments)


async def test_an_assignment_scope_is_unique_with_nulls_as_a_value(
    migrated_engine: AsyncEngine,
) -> None:
    role, user, project, fr = await _scoped_world(migrated_engine)
    insert = text(
        "INSERT INTO user_role_assignments (id, user_id, role_id, project_id, language_id) "
        "VALUES (:id, :user_id, :role_id, :project_id, :language_id)"
    )
    for project_id, language_id in ((None, None), (project.id, None), (None, fr.id)):
        with pytest.raises(IntegrityError, match="uq_user_role_assignments_scope"):
            async with migrated_engine.begin() as connection:
                await connection.execute(
                    insert,
                    {
                        "id": uuid4(),
                        "user_id": user.id,
                        "role_id": role.id,
                        "project_id": project_id,
                        "language_id": language_id,
                    },
                )


async def test_assignments_go_with_their_project_or_language(
    migrated_engine: AsyncEngine,
) -> None:
    _, user, project, fr = await _scoped_world(migrated_engine)
    async with migrated_engine.begin() as connection:
        await connection.execute(text("DELETE FROM projects WHERE id = :id"), {"id": project.id})
    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        after_project = await uow.users.get(user.id)
    assert after_project is not None
    assert [(a.project_id, a.language_id) for a in after_project.assignments] == [
        (None, None),
        (None, fr.id),
    ]
    async with migrated_engine.begin() as connection:
        await connection.execute(text("DELETE FROM languages WHERE id = :id"), {"id": fr.id})
    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        after_language = await uow.users.get(user.id)
    assert after_language is not None
    assert [(a.project_id, a.language_id) for a in after_language.assignments] == [(None, None)]


async def test_the_bootstrap_admin_is_assigned_globally(migrated_engine: AsyncEngine) -> None:
    container = Container(
        partial(SqlAlchemyUnitOfWork, migrated_engine),
        audio_storage=InMemoryAudioStorage(),
        audio_probe=FakeAudioProbe(),
        audio_policy=AUDIO_POLICY,
    )
    for _ in range(2):
        await container.run(container.build_bootstrap_admin, BootstrapAdminCommand("root@x.org"))
    async with migrated_engine.connect() as connection:
        rows = (
            await connection.execute(
                text("SELECT project_id, language_id FROM user_role_assignments")
            )
        ).all()
    assert [tuple(row) for row in rows] == [(None, None)]
