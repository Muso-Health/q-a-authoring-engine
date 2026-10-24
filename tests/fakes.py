from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Self

from config.container import Container
from qa_authoring.domain.model.intent import normalize_intent_text
from qa_authoring.domain.value_objects.naming import normalize_key

if TYPE_CHECKING:
    from types import TracebackType
    from uuid import UUID

    from qa_authoring.application.ports.category_repository import CategoryRepository
    from qa_authoring.application.ports.intent_repository import IntentRepository
    from qa_authoring.application.ports.language_repository import LanguageRepository
    from qa_authoring.application.ports.project_repository import ProjectRepository
    from qa_authoring.application.ports.protocol_repository import ProtocolRepository
    from qa_authoring.application.ports.qaset_repository import QASetRepository
    from qa_authoring.application.ports.theme_repository import ThemeRepository
    from qa_authoring.domain.model.category import Category
    from qa_authoring.domain.model.intent import Intent
    from qa_authoring.domain.model.language import Language
    from qa_authoring.domain.model.project import Project
    from qa_authoring.domain.model.protocol import Protocol
    from qa_authoring.domain.model.qaset import QASet
    from qa_authoring.domain.model.theme import Theme
    from qa_authoring.domain.value_objects.language_code import LanguageCode


class InMemoryLanguageRepository:
    def __init__(self) -> None:
        self.rows: dict[UUID, Language] = {}

    async def add(self, language: Language) -> None:
        self.rows[language.id] = language

    async def get(self, language_id: UUID) -> Language | None:
        return self.rows.get(language_id)

    async def find_by_code(self, code: LanguageCode) -> Language | None:
        return next((row for row in self.rows.values() if row.code == code), None)

    async def list(self) -> tuple[Language, ...]:
        return tuple(sorted(self.rows.values(), key=lambda row: row.code.value))

    async def update(self, language: Language) -> None:
        self.rows[language.id] = language

    async def delete(self, language_id: UUID) -> None:
        self.rows.pop(language_id, None)


class InMemoryProjectRepository:
    def __init__(self) -> None:
        self.rows: dict[UUID, Project] = {}

    async def add(self, project: Project) -> None:
        self.rows[project.id] = project

    async def get(self, project_id: UUID) -> Project | None:
        return self.rows.get(project_id)

    async def list(self) -> tuple[Project, ...]:
        return tuple(sorted(self.rows.values(), key=lambda row: (row.name, str(row.id))))

    async def update(self, project: Project) -> None:
        self.rows[project.id] = project

    async def delete(self, project_id: UUID) -> None:
        self.rows.pop(project_id, None)

    async def uses_base_language(self, language_id: UUID) -> bool:
        return any(row.base_language_id == language_id for row in self.rows.values())


class InMemoryProtocolRepository:
    def __init__(self) -> None:
        self.rows: dict[UUID, Protocol] = {}

    async def add(self, protocol: Protocol) -> None:
        self.rows[protocol.id] = protocol

    async def get(self, protocol_id: UUID) -> Protocol | None:
        return self.rows.get(protocol_id)

    async def list_by_project(self, project_id: UUID) -> tuple[Protocol, ...]:
        rows = [row for row in self.rows.values() if row.project_id == project_id]
        return tuple(sorted(rows, key=lambda row: (row.name, str(row.id))))

    async def update(self, protocol: Protocol) -> None:
        self.rows[protocol.id] = protocol

    async def delete(self, protocol_id: UUID) -> None:
        self.rows.pop(protocol_id, None)

    async def exists_for_project(self, project_id: UUID) -> bool:
        return any(row.project_id == project_id for row in self.rows.values())


class InMemoryThemeRepository:
    def __init__(self) -> None:
        self.rows: dict[UUID, Theme] = {}

    async def add(self, theme: Theme) -> None:
        self.rows[theme.id] = theme

    async def get(self, theme_id: UUID) -> Theme | None:
        return self.rows.get(theme_id)

    async def list_by_protocol(self, protocol_id: UUID) -> tuple[Theme, ...]:
        rows = [row for row in self.rows.values() if row.protocol_id == protocol_id]
        return tuple(sorted(rows, key=lambda row: (row.name, str(row.id))))

    async def update(self, theme: Theme) -> None:
        self.rows[theme.id] = theme

    async def delete(self, theme_id: UUID) -> None:
        self.rows.pop(theme_id, None)

    async def exists_for_protocol(self, protocol_id: UUID) -> bool:
        return any(row.protocol_id == protocol_id for row in self.rows.values())


class InMemoryQASetRepository:
    """Stores copies, so a handler that forgets to ``save`` loses its changes — as in the DB."""

    def __init__(self) -> None:
        self.rows: dict[UUID, QASet] = {}

    async def add(self, qaset: QASet) -> None:
        self.rows[qaset.id] = deepcopy(qaset)

    async def get(self, qaset_id: UUID) -> QASet | None:
        row = self.rows.get(qaset_id)
        return None if row is None else deepcopy(row)

    async def list_by_theme(self, theme_id: UUID) -> tuple[QASet, ...]:
        rows = [row for row in self.rows.values() if row.theme_id == theme_id]
        return tuple(deepcopy(row) for row in sorted(rows, key=lambda row: str(row.id)))

    async def save(self, qaset: QASet) -> None:
        self.rows[qaset.id] = deepcopy(qaset)

    async def delete(self, qaset_id: UUID) -> None:
        self.rows.pop(qaset_id, None)

    async def exists_for_theme(self, theme_id: UUID) -> bool:
        return any(row.theme_id == theme_id for row in self.rows.values())

    async def uses_language(self, language_id: UUID) -> bool:
        return any(
            p.language_id == language_id for row in self.rows.values() for p in row.presences()
        )

    async def uses_intent(self, intent_id: UUID) -> bool:
        return any(row.uses_intent(intent_id) for row in self.rows.values())

    async def uses_category(self, category_id: UUID) -> bool:
        return any(row.uses_category(category_id) for row in self.rows.values())


class InMemoryIntentRepository:
    def __init__(self) -> None:
        self.rows: dict[UUID, Intent] = {}

    async def get_or_create(self, intent: Intent) -> tuple[Intent, bool]:
        existing = next((row for row in self.rows.values() if row.key == intent.key), None)
        if existing is not None:
            return existing, False
        self.rows[intent.id] = intent
        return intent, True

    async def get(self, intent_id: UUID) -> Intent | None:
        return self.rows.get(intent_id)

    async def get_many(self, intent_ids: set[UUID]) -> dict[UUID, Intent]:
        return {i: self.rows[i] for i in intent_ids if i in self.rows}

    async def list(self, prefix: str | None = None) -> tuple[Intent, ...]:
        key = normalize_intent_text(prefix or "")
        rows = [row for row in self.rows.values() if row.key.startswith(key)]
        return tuple(sorted(rows, key=lambda row: (row.key, str(row.id))))

    async def delete(self, intent_id: UUID) -> None:
        self.rows.pop(intent_id, None)


class InMemoryCategoryRepository:
    def __init__(self) -> None:
        self.rows: dict[UUID, Category] = {}

    async def get_or_create(self, category: Category) -> tuple[Category, bool]:
        existing = next((row for row in self.rows.values() if row.key == category.key), None)
        if existing is not None:
            return existing, False
        self.rows[category.id] = category
        return category, True

    async def get(self, category_id: UUID) -> Category | None:
        return self.rows.get(category_id)

    async def get_many(self, category_ids: set[UUID]) -> dict[UUID, Category]:
        return {i: self.rows[i] for i in category_ids if i in self.rows}

    async def list(self, prefix: str | None = None) -> tuple[Category, ...]:
        key = normalize_key(prefix or "")
        rows = [row for row in self.rows.values() if row.key.startswith(key)]
        return tuple(sorted(rows, key=lambda row: (row.key, str(row.id))))

    async def delete(self, category_id: UUID) -> None:
        self.rows.pop(category_id, None)


@dataclass
class InMemoryStore:
    languages: InMemoryLanguageRepository = field(default_factory=InMemoryLanguageRepository)
    projects: InMemoryProjectRepository = field(default_factory=InMemoryProjectRepository)
    protocols: InMemoryProtocolRepository = field(default_factory=InMemoryProtocolRepository)
    themes: InMemoryThemeRepository = field(default_factory=InMemoryThemeRepository)
    qasets: InMemoryQASetRepository = field(default_factory=InMemoryQASetRepository)
    intents: InMemoryIntentRepository = field(default_factory=InMemoryIntentRepository)
    categories: InMemoryCategoryRepository = field(default_factory=InMemoryCategoryRepository)


class InMemoryUnitOfWork:
    languages: LanguageRepository
    projects: ProjectRepository
    protocols: ProtocolRepository
    themes: ThemeRepository
    qasets: QASetRepository
    intents: IntentRepository
    categories: CategoryRepository

    def __init__(self, store: InMemoryStore) -> None:
        self.languages = store.languages
        self.projects = store.projects
        self.protocols = store.protocols
        self.themes = store.themes
        self.qasets = store.qasets
        self.intents = store.intents
        self.categories = store.categories

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        return None


def in_memory_container() -> tuple[Container, InMemoryStore]:
    store = InMemoryStore()
    return Container(lambda: InMemoryUnitOfWork(store)), store
