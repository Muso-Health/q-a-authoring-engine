from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from qa_authoring.domain.model.category import Category
from qa_authoring.domain.model.qaset import CategoryNotAttachedError, QASet
from qa_authoring.domain.value_objects.naming import InvalidNameError, normalize_key


@pytest.mark.parametrize("name", ["Malaria", " malaria ", "MALARIA", "mAlArIa\n"])
def test_normalized_key_ignores_case_and_outer_whitespace(name: str) -> None:
    assert Category.register(name).key == "malaria"


def test_normalized_key_collapses_inner_whitespace() -> None:
    assert normalize_key("  Child \t health \n care ") == "child health care"
    assert Category.register(" Child   health ").key == "child health"


def test_register_keeps_the_trimmed_original_name() -> None:
    category = Category.register("  Child health ")
    assert isinstance(category.id, UUID)
    assert category.name == "Child health"


@pytest.mark.parametrize("name", ["", "   ", "\n\t"])
def test_name_must_not_be_blank(name: str) -> None:
    with pytest.raises(InvalidNameError):
        Category.register(name)


def _qaset() -> QASet:
    return QASet.create(theme_id=uuid4(), language_id=uuid4(), answer_text="a")


def test_add_category_is_idempotent_and_ordered() -> None:
    qaset = _qaset()
    first, second = uuid4(), uuid4()

    assert qaset.add_category(second) is True
    assert qaset.add_category(first) is True
    assert qaset.add_category(second) is False

    assert qaset.category_ids == (second, first)


def test_remove_category_removes_only_that_one() -> None:
    qaset = _qaset()
    kept, removed = uuid4(), uuid4()
    qaset.add_category(kept)
    qaset.add_category(removed)

    qaset.remove_category(removed)

    assert qaset.category_ids == (kept,)
    with pytest.raises(CategoryNotAttachedError):
        qaset.remove_category(removed)


def test_categories_belong_to_the_whole_qaset() -> None:
    language_id = uuid4()
    qaset = QASet.create(theme_id=uuid4(), language_id=language_id, answer_text="a")
    category_id = uuid4()
    qaset.add_category(category_id)

    qaset.add_language(uuid4(), "b")
    qaset.remove_language(language_id)

    assert qaset.category_ids == (category_id,)
    assert qaset.uses_category(category_id)
    assert not qaset.uses_category(uuid4())
