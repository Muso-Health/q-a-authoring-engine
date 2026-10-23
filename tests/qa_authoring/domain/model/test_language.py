from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from qa_authoring.domain.model.language import InvalidLanguageNameError, Language
from qa_authoring.domain.value_objects.language_code import LanguageCode


def test_register_assigns_a_surrogate_id_and_trims_the_name() -> None:
    language = Language.register(LanguageCode("bm"), "  Bambara  ")
    assert isinstance(language.id, UUID)
    assert language.code == LanguageCode("bm")
    assert language.name == "Bambara"


def test_each_registration_gets_its_own_id() -> None:
    assert (
        Language.register(LanguageCode("fr"), "French").id
        != Language.register(LanguageCode("fr"), "French").id
    )


@pytest.mark.parametrize("name", ["", "   ", "\t\n"])
def test_name_must_not_be_blank(name: str) -> None:
    with pytest.raises(InvalidLanguageNameError):
        Language.register(LanguageCode("fr"), name)


def test_rename_changes_the_name_only() -> None:
    language = Language.register(LanguageCode("fr"), "French")
    original_id = language.id

    language.rename("  Français ")

    assert language.name == "Français"
    assert language.code == LanguageCode("fr")
    assert language.id == original_id


def test_rename_rejects_a_blank_name_and_keeps_the_old_one() -> None:
    language = Language.register(LanguageCode("fr"), "French")
    with pytest.raises(InvalidLanguageNameError):
        language.rename("  ")
    assert language.name == "French"


def test_code_is_immutable() -> None:
    language = Language.register(LanguageCode("fr"), "French")
    with pytest.raises(AttributeError):
        language.code = LanguageCode("en")  # type: ignore[misc]
    assert language.code == LanguageCode("fr")


def test_equality_is_by_identity() -> None:
    language_id = uuid4()
    a = Language(language_id, LanguageCode("fr"), "French")
    b = Language(language_id, LanguageCode("fr"), "Français")
    assert a == b
    assert a != Language(uuid4(), LanguageCode("fr"), "French")
