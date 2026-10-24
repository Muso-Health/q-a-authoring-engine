from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from qa_authoring.application.add_category.command import AddCategoryCommand
from qa_authoring.application.add_category.handler import AddCategoryHandler
from qa_authoring.application.category_errors import CategoryInUseError, CategoryNotFoundError
from qa_authoring.application.delete_category.command import DeleteCategoryCommand
from qa_authoring.application.delete_category.handler import DeleteCategoryHandler
from qa_authoring.application.get_category.command import GetCategoryQuery
from qa_authoring.application.get_category.handler import GetCategoryHandler
from qa_authoring.application.get_qaset.command import GetQASetQuery
from qa_authoring.application.get_qaset.handler import GetQASetHandler
from qa_authoring.application.list_categories.command import ListCategoriesQuery
from qa_authoring.application.list_categories.handler import ListCategoriesHandler
from qa_authoring.application.qaset_errors import QASetNotFoundError
from qa_authoring.application.register_category.command import RegisterCategoryCommand
from qa_authoring.application.register_category.handler import RegisterCategoryHandler
from qa_authoring.application.remove_category.command import RemoveCategoryCommand
from qa_authoring.application.remove_category.handler import RemoveCategoryHandler
from qa_authoring.domain.model.qaset import CategoryNotAttachedError, QASet
from qa_authoring.domain.value_objects.naming import InvalidNameError
from tests.fakes import InMemoryStore, views


@pytest.fixture
def store() -> InMemoryStore:
    return InMemoryStore()


async def _register(store: InMemoryStore, name: str) -> UUID:
    result, _ = await RegisterCategoryHandler(store.categories)(RegisterCategoryCommand(name))
    return result.id


async def _qaset(store: InMemoryStore) -> QASet:
    qaset = QASet.create(theme_id=uuid4(), language_id=uuid4(), answer_text="a")
    await store.qasets.add(qaset)
    return qaset


def _add(store: InMemoryStore) -> AddCategoryHandler:
    return AddCategoryHandler(store.qasets, store.categories, views(store))


# --- catalogue ---


async def test_register_is_get_or_create_on_the_normalized_name(store: InMemoryStore) -> None:
    register = RegisterCategoryHandler(store.categories)

    created, was_created = await register(RegisterCategoryCommand(" Malaria "))
    again, created_again = await register(RegisterCategoryCommand("MALARIA"))

    assert (created.name, was_created) == ("Malaria", True)
    assert (again, created_again) == (created, False)
    assert len(store.categories.rows) == 1


async def test_register_rejects_blank_name(store: InMemoryStore) -> None:
    with pytest.raises(InvalidNameError):
        await RegisterCategoryHandler(store.categories)(RegisterCategoryCommand("  "))


async def test_list_filters_by_normalized_prefix(store: InMemoryStore) -> None:
    for name in ("Nutrition", "Child health", "child hygiene", "Malaria"):
        await _register(store, name)
    list_categories = ListCategoriesHandler(store.categories)

    everything = await list_categories(ListCategoriesQuery())
    child = await list_categories(ListCategoriesQuery(prefix="  CHILD  h"))

    assert [c.name for c in everything] == ["Child health", "child hygiene", "Malaria", "Nutrition"]
    assert [c.name for c in child] == ["Child health", "child hygiene"]


async def test_get_category(store: InMemoryStore) -> None:
    category_id = await _register(store, "Malaria")
    get = GetCategoryHandler(store.categories)
    assert (await get(GetCategoryQuery(category_id))).name == "Malaria"
    with pytest.raises(CategoryNotFoundError):
        await get(GetCategoryQuery(uuid4()))


async def test_delete_category_is_guarded_while_attached(store: InMemoryStore) -> None:
    category_id = await _register(store, "Malaria")
    qaset = await _qaset(store)
    await _add(store)(AddCategoryCommand(qaset_id=qaset.id, category_id=category_id))
    delete = DeleteCategoryHandler(store.categories, store.qasets)

    with pytest.raises(CategoryInUseError):
        await delete(DeleteCategoryCommand(category_id))
    assert category_id in store.categories.rows

    await RemoveCategoryHandler(store.qasets)(
        RemoveCategoryCommand(qaset_id=qaset.id, category_id=category_id)
    )
    await delete(DeleteCategoryCommand(category_id))
    assert category_id not in store.categories.rows
    with pytest.raises(CategoryNotFoundError):
        await delete(DeleteCategoryCommand(category_id))


# --- attachment ---


async def test_add_validates_qaset_and_category(store: InMemoryStore) -> None:
    category_id = await _register(store, "Malaria")
    qaset = await _qaset(store)
    with pytest.raises(CategoryNotFoundError):
        await _add(store)(AddCategoryCommand(qaset_id=qaset.id, category_id=uuid4()))
    with pytest.raises(QASetNotFoundError):
        await _add(store)(AddCategoryCommand(qaset_id=uuid4(), category_id=category_id))
    assert store.qasets.rows[qaset.id].category_ids == ()


async def test_add_twice_is_idempotent_and_returns_the_qaset(store: InMemoryStore) -> None:
    category_id = await _register(store, "Malaria")
    qaset = await _qaset(store)

    result, created = await _add(store)(
        AddCategoryCommand(qaset_id=qaset.id, category_id=category_id)
    )
    again, created_again = await _add(store)(
        AddCategoryCommand(qaset_id=qaset.id, category_id=category_id)
    )

    assert (created, created_again) == (True, False)
    assert result == again
    assert result.id == qaset.id
    assert [(c.category_id, c.name) for c in result.categories] == [(category_id, "Malaria")]
    assert store.qasets.rows[qaset.id].category_ids == (category_id,)


async def test_remove_only_that_attachment(store: InMemoryStore) -> None:
    kept, removed = await _register(store, "Malaria"), await _register(store, "Nutrition")
    qaset = await _qaset(store)
    for category_id in (kept, removed):
        await _add(store)(AddCategoryCommand(qaset_id=qaset.id, category_id=category_id))
    remove = RemoveCategoryHandler(store.qasets)

    await remove(RemoveCategoryCommand(qaset_id=qaset.id, category_id=removed))

    assert store.qasets.rows[qaset.id].category_ids == (kept,)
    with pytest.raises(CategoryNotAttachedError):
        await remove(RemoveCategoryCommand(qaset_id=qaset.id, category_id=removed))
    with pytest.raises(QASetNotFoundError):
        await remove(RemoveCategoryCommand(qaset_id=uuid4(), category_id=kept))


async def test_get_qaset_shows_categories_in_attachment_order(store: InMemoryStore) -> None:
    first, second = await _register(store, "Nutrition"), await _register(store, "Malaria")
    qaset = await _qaset(store)
    for category_id in (first, second):
        await _add(store)(AddCategoryCommand(qaset_id=qaset.id, category_id=category_id))

    result = await GetQASetHandler(store.qasets, views(store))(GetQASetQuery(qaset.id))

    assert [(c.category_id, c.name) for c in result.categories] == [
        (first, "Nutrition"),
        (second, "Malaria"),
    ]
