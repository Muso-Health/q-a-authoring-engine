from __future__ import annotations

from uuid import uuid4

import pytest

from qa_authoring.domain.model.permission import (
    Permission,
    UnknownPermissionError,
    parse_permissions,
)
from qa_authoring.domain.model.role import Role
from qa_authoring.domain.model.user import (
    InvalidEmailError,
    SubjectMismatchError,
    User,
    effective_permissions,
)
from qa_authoring.domain.value_objects.naming import InvalidNameError


def test_the_catalogue_is_fixed() -> None:
    assert {p.value for p in Permission} == {
        "manage_languages",
        "manage_catalog",
        "author_qasets",
        "manage_intents",
        "manage_categories",
        "manage_audio",
        "validate_clinical",
        "validate_translation",
        "validate_audio",
        "manage_access",
        "manage_prompts",
        "export_corpus",
    }


def test_parse_permissions_accepts_known_codes() -> None:
    assert parse_permissions(["author_qasets", "manage_audio", "author_qasets"]) == frozenset(
        {Permission.AUTHOR_QASETS, Permission.MANAGE_AUDIO}
    )


@pytest.mark.parametrize("codes", [["author_qasets", "fly"], ["MANAGE_AUDIO"], [""]])
def test_parse_permissions_rejects_unknown_codes(codes: list[str]) -> None:
    with pytest.raises(UnknownPermissionError) as raised:
        parse_permissions(codes)
    assert raised.value.codes


def test_role_name_is_normalized_for_uniqueness() -> None:
    role = Role.create(name="  Clinical   Reviewer ", permissions=[Permission.VALIDATE_CLINICAL])
    assert role.name == "Clinical   Reviewer"
    assert role.key == "clinical reviewer"
    assert role.permissions == frozenset({Permission.VALIDATE_CLINICAL})


def test_role_name_must_not_be_blank() -> None:
    with pytest.raises(InvalidNameError):
        Role.create(name=" ", permissions=[])


def test_role_rename_and_replace_permissions() -> None:
    role = Role.create(name="Author", permissions=[Permission.AUTHOR_QASETS])
    role.rename("Senior author")
    role.replace_permissions([Permission.AUTHOR_QASETS, Permission.MANAGE_AUDIO])
    assert (role.name, role.permissions) == (
        "Senior author",
        frozenset({Permission.AUTHOR_QASETS, Permission.MANAGE_AUDIO}),
    )


def test_user_email_is_normalized() -> None:
    user = User.create(email="  Ada.Lovelace@Example.ORG ", display_name=" Ada ")
    assert (user.email, user.display_name, user.is_active, user.subject) == (
        "ada.lovelace@example.org",
        "Ada",
        True,
        None,
    )


@pytest.mark.parametrize("email", ["", "ada", "@example.org", "ada@", "a da@example.org"])
def test_user_email_is_validated(email: str) -> None:
    with pytest.raises(InvalidEmailError):
        User.create(email=email, display_name="Ada")


def test_user_activation() -> None:
    user = User.create(email="ada@example.org", display_name="Ada")
    user.set_active(False)
    assert not user.is_active
    user.set_active(True)
    assert user.is_active


def test_role_assignment_is_idempotent() -> None:
    user = User.create(email="ada@example.org", display_name="Ada")
    first, second = uuid4(), uuid4()
    assert user.assign_role(first) is True
    assert user.assign_role(second) is True
    assert user.assign_role(first) is False
    assert user.role_ids == (first, second)
    assert user.unassign_role(first) is True
    assert user.unassign_role(first) is False
    assert list(user.role_ids) == [second]


def test_subject_is_bound_once() -> None:
    user = User.create(email="ada@example.org", display_name="Ada")
    assert user.bind_subject("accounts.google.com:1") is True
    assert user.bind_subject("accounts.google.com:1") is False
    with pytest.raises(SubjectMismatchError):
        user.bind_subject("accounts.google.com:2")
    assert user.subject == "accounts.google.com:1"


def test_effective_permissions_are_the_union_of_the_roles() -> None:
    author = Role.create(name="Author", permissions=[Permission.AUTHOR_QASETS])
    recorder = Role.create(
        name="Recorder", permissions=[Permission.MANAGE_AUDIO, Permission.AUTHOR_QASETS]
    )
    other = Role.create(name="Admin", permissions=list(Permission))
    user = User.create(email="ada@example.org", display_name="Ada")
    user.assign_role(author.id)
    user.assign_role(recorder.id)

    assert effective_permissions(user, [author, recorder, other]) == frozenset(
        {Permission.AUTHOR_QASETS, Permission.MANAGE_AUDIO}
    )


def test_an_inactive_user_has_no_permissions() -> None:
    admin = Role.create(name="Admin", permissions=list(Permission))
    user = User.create(email="ada@example.org", display_name="Ada")
    user.assign_role(admin.id)
    user.set_active(False)
    assert effective_permissions(user, [admin]) == frozenset()
