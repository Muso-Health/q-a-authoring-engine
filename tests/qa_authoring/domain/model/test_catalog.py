from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import UUID, uuid4

import pytest

from qa_authoring.domain.model.project import Project
from qa_authoring.domain.model.protocol import Protocol
from qa_authoring.domain.model.theme import Theme
from qa_authoring.domain.value_objects.naming import InvalidNameError


def _project(name: str = "Malaria", description: str | None = None) -> Project:
    return Project.create(name=name, base_language_id=uuid4(), description=description)


def _protocol(name: str = "Triage", description: str | None = None) -> Protocol:
    return Protocol.create(project_id=uuid4(), name=name, description=description)


def _theme(name: str = "Fever", description: str | None = None) -> Theme:
    return Theme.create(protocol_id=uuid4(), name=name, description=description)


Factory = Callable[..., Any]
FACTORIES: list[Factory] = [_project, _protocol, _theme]


@pytest.mark.parametrize("factory", FACTORIES)
def test_create_assigns_an_id_and_trims(factory: Factory) -> None:
    entity = factory("  Name  ", "  Some text ")
    assert isinstance(entity.id, UUID)
    assert entity.name == "Name"
    assert entity.description == "Some text"


@pytest.mark.parametrize("factory", FACTORIES)
@pytest.mark.parametrize("name", ["", "   ", "\n\t"])
def test_name_must_not_be_blank(factory: Factory, name: str) -> None:
    with pytest.raises(InvalidNameError):
        factory(name)


@pytest.mark.parametrize("factory", FACTORIES)
@pytest.mark.parametrize("description", [None, "", "   "])
def test_blank_description_is_none(factory: Factory, description: str | None) -> None:
    assert factory("Name", description).description is None


@pytest.mark.parametrize("factory", FACTORIES)
def test_rename_and_describe(factory: Factory) -> None:
    entity = factory("Old", "Old text")
    entity.rename("  New ")
    entity.describe(" New text ")
    assert (entity.name, entity.description) == ("New", "New text")
    entity.describe(None)
    assert entity.description is None


@pytest.mark.parametrize("factory", FACTORIES)
def test_rename_rejects_blank_and_keeps_the_old_name(factory: Factory) -> None:
    entity = factory("Old")
    with pytest.raises(InvalidNameError):
        entity.rename(" ")
    assert entity.name == "Old"


@pytest.mark.parametrize("factory", FACTORIES)
def test_equality_is_by_identity(factory: Factory) -> None:
    a = factory("Same")
    b = factory("Same")
    assert a != b
    assert a == a


def test_project_keeps_its_base_language() -> None:
    language_id = uuid4()
    project = Project.create(name="Malaria", base_language_id=language_id)
    project.rename("Malaria v2")
    project.describe("updated")
    assert project.base_language_id == language_id


def test_project_base_language_is_immutable() -> None:
    project = _project()
    with pytest.raises(AttributeError):
        project.base_language_id = uuid4()  # type: ignore[misc]


def test_protocol_project_is_immutable() -> None:
    protocol = _protocol()
    with pytest.raises(AttributeError):
        protocol.project_id = uuid4()  # type: ignore[misc]


def test_theme_protocol_is_immutable() -> None:
    theme = _theme()
    with pytest.raises(AttributeError):
        theme.protocol_id = uuid4()  # type: ignore[misc]
