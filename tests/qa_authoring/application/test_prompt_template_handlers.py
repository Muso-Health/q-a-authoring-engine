from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from qa_authoring.application.get_prompt_template.command import GetPromptTemplateQuery
from qa_authoring.application.list_prompt_templates.command import ListPromptTemplatesQuery
from qa_authoring.application.prompt_template_errors import PromptTemplateNotFoundError
from qa_authoring.application.seed_prompt_templates.command import SeedPromptTemplatesCommand
from qa_authoring.application.update_prompt_template.command import (
    UpdatePromptTemplateCommand,
)
from qa_authoring.domain.model.permission import Permission
from qa_authoring.domain.model.prompt_template import (
    DEFAULT_TEMPLATES,
    REQUIRED_PLACEHOLDERS,
    InvalidPromptTemplateError,
    PromptRenderError,
    PromptTemplateKey,
    placeholders,
)
from tests.fakes import NOW, in_memory_container, seed_user

if TYPE_CHECKING:
    from config.container import Container
    from tests.fakes import InMemoryStore

TRANSLATION = "Translate {text} from {source_language} into {target_language}."


@pytest.fixture
def world() -> tuple[Container, InMemoryStore]:
    return in_memory_container()


async def _seed(container: Container) -> None:
    await container.run(container.build_seed_prompt_templates, SeedPromptTemplatesCommand())


def test_defaults_use_exactly_their_required_placeholders() -> None:
    assert set(DEFAULT_TEMPLATES) == set(PromptTemplateKey)
    for key, content in DEFAULT_TEMPLATES.items():
        assert placeholders(content) == REQUIRED_PLACEHOLDERS[key]


async def test_seeding_is_idempotent_and_never_overwrites_edits(
    world: tuple[Container, InMemoryStore],
) -> None:
    container, store = world
    editor = seed_user(store, "editor@example.org", Permission.MANAGE_PROMPTS).id

    await _seed(container)
    seeded = {
        k: (t.content, t.updated_by, t.updated_at) for k, t in store.prompt_templates.rows.items()
    }
    await container.run(
        container.build_update_prompt_template,
        UpdatePromptTemplateCommand("translation", TRANSLATION, actor_user_id=editor),
    )
    await _seed(container)

    assert set(seeded) == set(PromptTemplateKey)
    assert all(by is None and at == NOW for _, by, at in seeded.values())
    assert store.prompt_templates.rows[PromptTemplateKey.TRANSLATION].content == TRANSLATION
    variant = store.prompt_templates.rows[PromptTemplateKey.VARIANT_GENERATION]
    assert variant.content == DEFAULT_TEMPLATES[PromptTemplateKey.VARIANT_GENERATION]


async def test_list_and_get(world: tuple[Container, InMemoryStore]) -> None:
    container, _ = world
    await _seed(container)

    listed = await container.run(container.build_list_prompt_templates, ListPromptTemplatesQuery())
    got = await container.run(
        container.build_get_prompt_template, GetPromptTemplateQuery("variant_generation")
    )

    assert [t.key for t in listed] == ["completeness", "translation", "variant_generation"]
    assert got.key == "variant_generation"
    assert got.required_placeholders == ("answer", "context", "existing_questions", "language")
    assert (got.updated_by_email, got.updated_at) == (None, NOW)


async def test_unknown_or_missing_templates_are_not_found(
    world: tuple[Container, InMemoryStore],
) -> None:
    container, _ = world
    for key in ("summary", "TRANSLATION", "translation"):  # last: valid but not seeded
        with pytest.raises(PromptTemplateNotFoundError):
            await container.run(container.build_get_prompt_template, GetPromptTemplateQuery(key))
    with pytest.raises(PromptTemplateNotFoundError):
        await container.run(
            container.build_update_prompt_template,
            UpdatePromptTemplateCommand("summary", TRANSLATION, actor_user_id=uuid4()),
        )


async def test_update_records_the_editor(world: tuple[Container, InMemoryStore]) -> None:
    container, store = world
    editor = seed_user(store, "editor@example.org", Permission.MANAGE_PROMPTS).id
    await _seed(container)

    result = await container.run(
        container.build_update_prompt_template,
        UpdatePromptTemplateCommand("translation", TRANSLATION, actor_user_id=editor),
    )

    assert (result.content, result.updated_by_email, result.updated_at) == (
        TRANSLATION,
        "editor@example.org",
        NOW,
    )
    with pytest.raises(InvalidPromptTemplateError):
        await container.run(
            container.build_update_prompt_template,
            UpdatePromptTemplateCommand("translation", "Only {text}", actor_user_id=editor),
        )


async def test_update_creates_an_unseeded_fixed_key(world: tuple[Container, InMemoryStore]) -> None:
    container, store = world
    editor = seed_user(store, "editor@example.org", Permission.MANAGE_PROMPTS).id
    await container.run(
        container.build_update_prompt_template,
        UpdatePromptTemplateCommand("translation", TRANSLATION, actor_user_id=editor),
    )
    assert store.prompt_templates.rows[PromptTemplateKey.TRANSLATION].updated_by == editor


async def test_the_port_renders_the_active_template(world: tuple[Container, InMemoryStore]) -> None:
    container, store = world
    editor = seed_user(store, "editor@example.org", Permission.MANAGE_PROMPTS).id
    await _seed(container)
    values = {"source_language": "French", "target_language": "Bambara", "text": "Buvez de l'eau."}

    async def render() -> str:
        async with container.unit_of_work() as uow:
            port = container.prompt_templates(uow)
            return await port.render(PromptTemplateKey.TRANSLATION, values)

    assert "Buvez de l'eau." in await render()
    await container.run(
        container.build_update_prompt_template,
        UpdatePromptTemplateCommand("translation", TRANSLATION, actor_user_id=editor),
    )
    assert await render() == "Translate Buvez de l'eau. from French into Bambara."

    async with container.unit_of_work() as uow:
        with pytest.raises(PromptRenderError):
            await container.prompt_templates(uow).render(
                PromptTemplateKey.TRANSLATION, {"text": "x"}
            )


async def test_the_port_reports_a_missing_template(world: tuple[Container, InMemoryStore]) -> None:
    container, _ = world
    async with container.unit_of_work() as uow:
        with pytest.raises(PromptTemplateNotFoundError):
            await container.prompt_templates(uow).render(PromptTemplateKey.TRANSLATION, {})
