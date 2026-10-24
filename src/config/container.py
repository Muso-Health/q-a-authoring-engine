from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.add_category.handler import AddCategoryHandler
from qa_authoring.application.add_language_presence.handler import AddLanguagePresenceHandler
from qa_authoring.application.add_question_variant.handler import AddQuestionVariantHandler
from qa_authoring.application.attach_intent.handler import AttachIntentHandler
from qa_authoring.application.create_project.handler import CreateProjectHandler
from qa_authoring.application.create_protocol.handler import CreateProtocolHandler
from qa_authoring.application.create_qaset.handler import CreateQASetHandler
from qa_authoring.application.create_theme.handler import CreateThemeHandler
from qa_authoring.application.delete_category.handler import DeleteCategoryHandler
from qa_authoring.application.delete_intent.handler import DeleteIntentHandler
from qa_authoring.application.delete_language.handler import DeleteLanguageHandler
from qa_authoring.application.delete_project.handler import DeleteProjectHandler
from qa_authoring.application.delete_protocol.handler import DeleteProtocolHandler
from qa_authoring.application.delete_qaset.handler import DeleteQASetHandler
from qa_authoring.application.delete_question_variant.handler import DeleteQuestionVariantHandler
from qa_authoring.application.delete_theme.handler import DeleteThemeHandler
from qa_authoring.application.detach_intent.handler import DetachIntentHandler
from qa_authoring.application.get_category.handler import GetCategoryHandler
from qa_authoring.application.get_intent.handler import GetIntentHandler
from qa_authoring.application.get_language.handler import GetLanguageHandler
from qa_authoring.application.get_project.handler import GetProjectHandler
from qa_authoring.application.get_protocol.handler import GetProtocolHandler
from qa_authoring.application.get_qaset.handler import GetQASetHandler
from qa_authoring.application.get_theme.handler import GetThemeHandler
from qa_authoring.application.link_answers.handler import LinkAnswersHandler
from qa_authoring.application.link_variants.handler import LinkVariantsHandler
from qa_authoring.application.list_categories.handler import ListCategoriesHandler
from qa_authoring.application.list_intents.handler import ListIntentsHandler
from qa_authoring.application.list_languages.handler import ListLanguagesHandler
from qa_authoring.application.list_projects.handler import ListProjectsHandler
from qa_authoring.application.list_protocols.handler import ListProtocolsHandler
from qa_authoring.application.list_qasets.handler import ListQASetsHandler
from qa_authoring.application.list_themes.handler import ListThemesHandler
from qa_authoring.application.register_category.handler import RegisterCategoryHandler
from qa_authoring.application.register_intent.handler import RegisterIntentHandler
from qa_authoring.application.register_language.handler import RegisterLanguageHandler
from qa_authoring.application.remove_category.handler import RemoveCategoryHandler
from qa_authoring.application.remove_language_presence.handler import RemoveLanguagePresenceHandler
from qa_authoring.application.unlink_answers.handler import UnlinkAnswersHandler
from qa_authoring.application.unlink_variants.handler import UnlinkVariantsHandler
from qa_authoring.application.update_answer.handler import UpdateAnswerHandler
from qa_authoring.application.update_language.handler import UpdateLanguageHandler
from qa_authoring.application.update_project.handler import UpdateProjectHandler
from qa_authoring.application.update_protocol.handler import UpdateProtocolHandler
from qa_authoring.application.update_question_variant.handler import UpdateQuestionVariantHandler
from qa_authoring.application.update_theme.handler import UpdateThemeHandler

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from qa_authoring.application.ports.unit_of_work import UnitOfWork


class Container:
    """The DI container: builds each use-case handler over the repositories of a unit of work.

    ``run`` opens one unit of work per call — one transaction per use case. Framework-agnostic: the
    API edge reads it off ``app.state``. The unit-of-work factory is injected, so ``main.py`` wires
    the SQLAlchemy one and tests wire an in-memory one.
    """

    def __init__(self, unit_of_work: Callable[[], UnitOfWork]) -> None:
        self._unit_of_work = unit_of_work

    async def run[C, R](
        self,
        build: Callable[[UnitOfWork], Callable[[C], Awaitable[R]]],
        command: C,
    ) -> R:
        async with self._unit_of_work() as uow:
            return await build(uow)(command)

    def build_register_language(self, uow: UnitOfWork) -> RegisterLanguageHandler:
        return RegisterLanguageHandler(uow.languages)

    def build_list_languages(self, uow: UnitOfWork) -> ListLanguagesHandler:
        return ListLanguagesHandler(uow.languages)

    def build_get_language(self, uow: UnitOfWork) -> GetLanguageHandler:
        return GetLanguageHandler(uow.languages)

    def build_update_language(self, uow: UnitOfWork) -> UpdateLanguageHandler:
        return UpdateLanguageHandler(uow.languages)

    def build_delete_language(self, uow: UnitOfWork) -> DeleteLanguageHandler:
        return DeleteLanguageHandler(uow.languages, uow.projects, uow.qasets)

    def build_create_project(self, uow: UnitOfWork) -> CreateProjectHandler:
        return CreateProjectHandler(uow.projects, uow.languages)

    def build_list_projects(self, uow: UnitOfWork) -> ListProjectsHandler:
        return ListProjectsHandler(uow.projects)

    def build_get_project(self, uow: UnitOfWork) -> GetProjectHandler:
        return GetProjectHandler(uow.projects)

    def build_update_project(self, uow: UnitOfWork) -> UpdateProjectHandler:
        return UpdateProjectHandler(uow.projects)

    def build_delete_project(self, uow: UnitOfWork) -> DeleteProjectHandler:
        return DeleteProjectHandler(uow.projects, uow.protocols)

    def build_create_protocol(self, uow: UnitOfWork) -> CreateProtocolHandler:
        return CreateProtocolHandler(uow.protocols, uow.projects)

    def build_list_protocols(self, uow: UnitOfWork) -> ListProtocolsHandler:
        return ListProtocolsHandler(uow.protocols, uow.projects)

    def build_get_protocol(self, uow: UnitOfWork) -> GetProtocolHandler:
        return GetProtocolHandler(uow.protocols)

    def build_update_protocol(self, uow: UnitOfWork) -> UpdateProtocolHandler:
        return UpdateProtocolHandler(uow.protocols)

    def build_delete_protocol(self, uow: UnitOfWork) -> DeleteProtocolHandler:
        return DeleteProtocolHandler(uow.protocols, uow.themes)

    def build_create_theme(self, uow: UnitOfWork) -> CreateThemeHandler:
        return CreateThemeHandler(uow.themes, uow.protocols)

    def build_list_themes(self, uow: UnitOfWork) -> ListThemesHandler:
        return ListThemesHandler(uow.themes, uow.protocols)

    def build_get_theme(self, uow: UnitOfWork) -> GetThemeHandler:
        return GetThemeHandler(uow.themes)

    def build_update_theme(self, uow: UnitOfWork) -> UpdateThemeHandler:
        return UpdateThemeHandler(uow.themes)

    def build_delete_theme(self, uow: UnitOfWork) -> DeleteThemeHandler:
        return DeleteThemeHandler(uow.themes, uow.qasets)

    def build_create_qaset(self, uow: UnitOfWork) -> CreateQASetHandler:
        return CreateQASetHandler(uow.qasets, uow.themes, uow.languages)

    def build_add_language_presence(self, uow: UnitOfWork) -> AddLanguagePresenceHandler:
        return AddLanguagePresenceHandler(uow.qasets, uow.languages)

    def build_update_answer(self, uow: UnitOfWork) -> UpdateAnswerHandler:
        return UpdateAnswerHandler(uow.qasets, uow.intents)

    def build_remove_language_presence(self, uow: UnitOfWork) -> RemoveLanguagePresenceHandler:
        return RemoveLanguagePresenceHandler(uow.qasets)

    def build_add_question_variant(self, uow: UnitOfWork) -> AddQuestionVariantHandler:
        return AddQuestionVariantHandler(uow.qasets)

    def build_update_question_variant(self, uow: UnitOfWork) -> UpdateQuestionVariantHandler:
        return UpdateQuestionVariantHandler(uow.qasets, uow.intents)

    def build_delete_question_variant(self, uow: UnitOfWork) -> DeleteQuestionVariantHandler:
        return DeleteQuestionVariantHandler(uow.qasets)

    def build_get_qaset(self, uow: UnitOfWork) -> GetQASetHandler:
        return GetQASetHandler(uow.qasets, uow.intents, uow.categories)

    def build_list_qasets(self, uow: UnitOfWork) -> ListQASetsHandler:
        return ListQASetsHandler(uow.qasets, uow.themes)

    def build_delete_qaset(self, uow: UnitOfWork) -> DeleteQASetHandler:
        return DeleteQASetHandler(uow.qasets)

    def build_link_answers(self, uow: UnitOfWork) -> LinkAnswersHandler:
        return LinkAnswersHandler(uow.qasets)

    def build_unlink_answers(self, uow: UnitOfWork) -> UnlinkAnswersHandler:
        return UnlinkAnswersHandler(uow.qasets)

    def build_link_variants(self, uow: UnitOfWork) -> LinkVariantsHandler:
        return LinkVariantsHandler(uow.qasets)

    def build_unlink_variants(self, uow: UnitOfWork) -> UnlinkVariantsHandler:
        return UnlinkVariantsHandler(uow.qasets)

    def build_register_intent(self, uow: UnitOfWork) -> RegisterIntentHandler:
        return RegisterIntentHandler(uow.intents)

    def build_list_intents(self, uow: UnitOfWork) -> ListIntentsHandler:
        return ListIntentsHandler(uow.intents)

    def build_get_intent(self, uow: UnitOfWork) -> GetIntentHandler:
        return GetIntentHandler(uow.intents)

    def build_delete_intent(self, uow: UnitOfWork) -> DeleteIntentHandler:
        return DeleteIntentHandler(uow.intents, uow.qasets)

    def build_attach_intent(self, uow: UnitOfWork) -> AttachIntentHandler:
        return AttachIntentHandler(uow.qasets, uow.intents)

    def build_detach_intent(self, uow: UnitOfWork) -> DetachIntentHandler:
        return DetachIntentHandler(uow.qasets)

    def build_register_category(self, uow: UnitOfWork) -> RegisterCategoryHandler:
        return RegisterCategoryHandler(uow.categories)

    def build_list_categories(self, uow: UnitOfWork) -> ListCategoriesHandler:
        return ListCategoriesHandler(uow.categories)

    def build_get_category(self, uow: UnitOfWork) -> GetCategoryHandler:
        return GetCategoryHandler(uow.categories)

    def build_delete_category(self, uow: UnitOfWork) -> DeleteCategoryHandler:
        return DeleteCategoryHandler(uow.categories, uow.qasets)

    def build_add_category(self, uow: UnitOfWork) -> AddCategoryHandler:
        return AddCategoryHandler(uow.qasets, uow.intents, uow.categories)

    def build_remove_category(self, uow: UnitOfWork) -> RemoveCategoryHandler:
        return RemoveCategoryHandler(uow.qasets)
