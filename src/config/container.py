from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from qa_authoring.application.add_category.handler import AddCategoryHandler
from qa_authoring.application.add_language_presence.handler import AddLanguagePresenceHandler
from qa_authoring.application.add_question_variant.handler import AddQuestionVariantHandler
from qa_authoring.application.assign_role.handler import AssignRoleHandler
from qa_authoring.application.attach_intent.handler import AttachIntentHandler
from qa_authoring.application.audio_upload import AudioUploader
from qa_authoring.application.bootstrap_admin.handler import BootstrapAdminHandler
from qa_authoring.application.create_project.handler import CreateProjectHandler
from qa_authoring.application.create_protocol.handler import CreateProtocolHandler
from qa_authoring.application.create_qaset.handler import CreateQASetHandler
from qa_authoring.application.create_role.handler import CreateRoleHandler
from qa_authoring.application.create_theme.handler import CreateThemeHandler
from qa_authoring.application.create_user.handler import CreateUserHandler
from qa_authoring.application.delete_answer_audio.handler import DeleteAnswerAudioHandler
from qa_authoring.application.delete_category.handler import DeleteCategoryHandler
from qa_authoring.application.delete_intent.handler import DeleteIntentHandler
from qa_authoring.application.delete_language.handler import DeleteLanguageHandler
from qa_authoring.application.delete_project.handler import DeleteProjectHandler
from qa_authoring.application.delete_protocol.handler import DeleteProtocolHandler
from qa_authoring.application.delete_qaset.handler import DeleteQASetHandler
from qa_authoring.application.delete_question_variant.handler import DeleteQuestionVariantHandler
from qa_authoring.application.delete_role.handler import DeleteRoleHandler
from qa_authoring.application.delete_theme.handler import DeleteThemeHandler
from qa_authoring.application.delete_variant_audio.handler import DeleteVariantAudioHandler
from qa_authoring.application.detach_intent.handler import DetachIntentHandler
from qa_authoring.application.get_audio.handler import GetAudioHandler
from qa_authoring.application.get_audio_playback_url.handler import GetAudioPlaybackUrlHandler
from qa_authoring.application.get_audio_validation.handler import GetAudioValidationHandler
from qa_authoring.application.get_category.handler import GetCategoryHandler
from qa_authoring.application.get_clinical_validation.handler import GetClinicalValidationHandler
from qa_authoring.application.get_intent.handler import GetIntentHandler
from qa_authoring.application.get_language.handler import GetLanguageHandler
from qa_authoring.application.get_project.handler import GetProjectHandler
from qa_authoring.application.get_prompt_template.handler import GetPromptTemplateHandler
from qa_authoring.application.get_protocol.handler import GetProtocolHandler
from qa_authoring.application.get_qaset.handler import GetQASetHandler
from qa_authoring.application.get_role.handler import GetRoleHandler
from qa_authoring.application.get_theme.handler import GetThemeHandler
from qa_authoring.application.get_translation_validation.handler import (
    GetTranslationValidationHandler,
)
from qa_authoring.application.get_user.handler import GetUserHandler
from qa_authoring.application.link_answers.handler import LinkAnswersHandler
from qa_authoring.application.link_variants.handler import LinkVariantsHandler
from qa_authoring.application.list_categories.handler import ListCategoriesHandler
from qa_authoring.application.list_intents.handler import ListIntentsHandler
from qa_authoring.application.list_languages.handler import ListLanguagesHandler
from qa_authoring.application.list_projects.handler import ListProjectsHandler
from qa_authoring.application.list_prompt_templates.handler import ListPromptTemplatesHandler
from qa_authoring.application.list_protocols.handler import ListProtocolsHandler
from qa_authoring.application.list_qasets.handler import ListQASetsHandler
from qa_authoring.application.list_roles.handler import ListRolesHandler
from qa_authoring.application.list_themes.handler import ListThemesHandler
from qa_authoring.application.list_users.handler import ListUsersHandler
from qa_authoring.application.prompt_templates import PromptRenderer
from qa_authoring.application.qaset_views import QASetViews
from qa_authoring.application.record_audio_decision.handler import RecordAudioDecisionHandler
from qa_authoring.application.record_clinical_decision.handler import RecordClinicalDecisionHandler
from qa_authoring.application.record_translation_decision.handler import (
    RecordTranslationDecisionHandler,
)
from qa_authoring.application.register_category.handler import RegisterCategoryHandler
from qa_authoring.application.register_intent.handler import RegisterIntentHandler
from qa_authoring.application.register_language.handler import RegisterLanguageHandler
from qa_authoring.application.remove_category.handler import RemoveCategoryHandler
from qa_authoring.application.remove_language_presence.handler import RemoveLanguagePresenceHandler
from qa_authoring.application.resolve_current_user.handler import ResolveCurrentUserHandler
from qa_authoring.application.seed_prompt_templates.handler import SeedPromptTemplatesHandler
from qa_authoring.application.set_answer_audio.handler import SetAnswerAudioHandler
from qa_authoring.application.set_variant_audio.handler import SetVariantAudioHandler
from qa_authoring.application.translate_answer.handler import TranslateAnswerHandler
from qa_authoring.application.translate_variant.handler import TranslateVariantHandler
from qa_authoring.application.translation_engines import TranslationEngine, Translators
from qa_authoring.application.unassign_role.handler import UnassignRoleHandler
from qa_authoring.application.unlink_answers.handler import UnlinkAnswersHandler
from qa_authoring.application.unlink_variants.handler import UnlinkVariantsHandler
from qa_authoring.application.update_answer.handler import UpdateAnswerHandler
from qa_authoring.application.update_language.handler import UpdateLanguageHandler
from qa_authoring.application.update_project.handler import UpdateProjectHandler
from qa_authoring.application.update_prompt_template.handler import UpdatePromptTemplateHandler
from qa_authoring.application.update_protocol.handler import UpdateProtocolHandler
from qa_authoring.application.update_question_variant.handler import UpdateQuestionVariantHandler
from qa_authoring.application.update_role.handler import UpdateRoleHandler
from qa_authoring.application.update_theme.handler import UpdateThemeHandler
from qa_authoring.application.update_user.handler import UpdateUserHandler
from qa_authoring.application.validation_reset import ValidationResetter
from qa_authoring.application.validation_support import BaseLanguageResolver, DecisionRecorder
from qa_authoring.infrastructure.translation.llm_translator import LlmTranslator

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from qa_authoring.application.audio_policy import AudioPolicy
    from qa_authoring.application.ports.audio_probe import AudioProbePort
    from qa_authoring.application.ports.audio_storage import AudioStoragePort
    from qa_authoring.application.ports.llm import LlmPort
    from qa_authoring.application.ports.prompt_templates import PromptTemplatePort
    from qa_authoring.application.ports.translator import TranslatorPort
    from qa_authoring.application.ports.unit_of_work import UnitOfWork


class Container:
    """The DI container: builds each use-case handler over the repositories of a unit of work.

    ``run`` opens one unit of work per call — one transaction per use case. Framework-agnostic: the
    API edge reads it off ``app.state``. The unit-of-work factory and the audio adapters are
    injected, so ``main.py`` wires the real ones and tests wire in-memory fakes.
    """

    def __init__(
        self,
        unit_of_work: Callable[[], UnitOfWork],
        *,
        audio_storage: AudioStoragePort,
        audio_probe: AudioProbePort,
        audio_policy: AudioPolicy,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        llm: LlmPort | None = None,
        google_translator: TranslatorPort | None = None,
    ) -> None:
        self._unit_of_work = unit_of_work
        self._llm = llm
        self._google_translator = google_translator
        self._audio_storage = audio_storage
        self._audio_policy = audio_policy
        self._clock = clock
        self._audio_uploader = AudioUploader(audio_storage, audio_probe, audio_policy, clock)

    @property
    def audio_policy(self) -> AudioPolicy:
        return self._audio_policy

    def unit_of_work(self) -> UnitOfWork:
        """A unit of work for a use case that composes several ports itself."""
        return self._unit_of_work()

    @staticmethod
    def prompt_templates(uow: UnitOfWork) -> PromptTemplatePort:
        return PromptRenderer(uow.prompt_templates)

    @staticmethod
    def _views(uow: UnitOfWork) -> QASetViews:
        return QASetViews(uow.intents, uow.categories, uow.validations)

    @staticmethod
    def _base_language(uow: UnitOfWork) -> BaseLanguageResolver:
        return BaseLanguageResolver(uow.themes, uow.protocols, uow.projects)

    def _resetter(self, uow: UnitOfWork) -> ValidationResetter:
        return ValidationResetter(uow.validations, self._base_language(uow), self._clock)

    def _translators(self, uow: UnitOfWork) -> Translators:
        """The engines this deployment can use; a missing one is an unknown engine."""
        engines: dict[TranslationEngine, TranslatorPort] = {}
        if self._llm is not None:
            engines[TranslationEngine.LLM] = LlmTranslator(self.prompt_templates(uow), self._llm)
        if self._google_translator is not None:
            engines[TranslationEngine.GOOGLE] = self._google_translator
        return Translators(engines)

    def _recorder(self, uow: UnitOfWork) -> DecisionRecorder:
        return DecisionRecorder(uow.validations, uow.users, self._clock)

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
        return UpdateAnswerHandler(uow.qasets, self._views(uow), self._resetter(uow))

    def build_remove_language_presence(self, uow: UnitOfWork) -> RemoveLanguagePresenceHandler:
        return RemoveLanguagePresenceHandler(uow.qasets, self._resetter(uow))

    def build_add_question_variant(self, uow: UnitOfWork) -> AddQuestionVariantHandler:
        return AddQuestionVariantHandler(uow.qasets, self._resetter(uow))

    def build_update_question_variant(self, uow: UnitOfWork) -> UpdateQuestionVariantHandler:
        return UpdateQuestionVariantHandler(uow.qasets, self._views(uow), self._resetter(uow))

    def build_delete_question_variant(self, uow: UnitOfWork) -> DeleteQuestionVariantHandler:
        return DeleteQuestionVariantHandler(uow.qasets, self._resetter(uow))

    def build_get_qaset(self, uow: UnitOfWork) -> GetQASetHandler:
        return GetQASetHandler(uow.qasets, self._views(uow))

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
        return AttachIntentHandler(uow.qasets, uow.intents, self._views(uow))

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
        return AddCategoryHandler(uow.qasets, uow.categories, self._views(uow))

    def build_remove_category(self, uow: UnitOfWork) -> RemoveCategoryHandler:
        return RemoveCategoryHandler(uow.qasets)

    def build_set_answer_audio(self, uow: UnitOfWork) -> SetAnswerAudioHandler:
        return SetAnswerAudioHandler(
            uow.qasets, self._audio_uploader, self._audio_storage, uow.after_commit
        )

    def build_set_variant_audio(self, uow: UnitOfWork) -> SetVariantAudioHandler:
        return SetVariantAudioHandler(
            uow.qasets, self._audio_uploader, self._audio_storage, uow.after_commit
        )

    def build_delete_answer_audio(self, uow: UnitOfWork) -> DeleteAnswerAudioHandler:
        return DeleteAnswerAudioHandler(uow.qasets, self._audio_storage, uow.after_commit)

    def build_delete_variant_audio(self, uow: UnitOfWork) -> DeleteVariantAudioHandler:
        return DeleteVariantAudioHandler(uow.qasets, self._audio_storage, uow.after_commit)

    def build_get_audio(self, uow: UnitOfWork) -> GetAudioHandler:
        return GetAudioHandler(uow.qasets)

    def build_get_audio_playback_url(self, uow: UnitOfWork) -> GetAudioPlaybackUrlHandler:
        return GetAudioPlaybackUrlHandler(
            uow.qasets, self._audio_storage, self._audio_policy, self._clock
        )

    def build_create_user(self, uow: UnitOfWork) -> CreateUserHandler:
        return CreateUserHandler(uow.users)

    def build_list_users(self, uow: UnitOfWork) -> ListUsersHandler:
        return ListUsersHandler(uow.users, uow.roles)

    def build_get_user(self, uow: UnitOfWork) -> GetUserHandler:
        return GetUserHandler(uow.users, uow.roles)

    def build_update_user(self, uow: UnitOfWork) -> UpdateUserHandler:
        return UpdateUserHandler(uow.users, uow.roles)

    def build_assign_role(self, uow: UnitOfWork) -> AssignRoleHandler:
        return AssignRoleHandler(uow.users, uow.roles)

    def build_unassign_role(self, uow: UnitOfWork) -> UnassignRoleHandler:
        return UnassignRoleHandler(uow.users, uow.roles)

    def build_create_role(self, uow: UnitOfWork) -> CreateRoleHandler:
        return CreateRoleHandler(uow.roles)

    def build_list_roles(self, uow: UnitOfWork) -> ListRolesHandler:
        return ListRolesHandler(uow.roles)

    def build_get_role(self, uow: UnitOfWork) -> GetRoleHandler:
        return GetRoleHandler(uow.roles)

    def build_update_role(self, uow: UnitOfWork) -> UpdateRoleHandler:
        return UpdateRoleHandler(uow.roles)

    def build_delete_role(self, uow: UnitOfWork) -> DeleteRoleHandler:
        return DeleteRoleHandler(uow.roles, uow.users)

    def build_resolve_current_user(self, uow: UnitOfWork) -> ResolveCurrentUserHandler:
        return ResolveCurrentUserHandler(uow.users, uow.roles)

    def build_bootstrap_admin(self, uow: UnitOfWork) -> BootstrapAdminHandler:
        return BootstrapAdminHandler(uow.users, uow.roles)

    def build_record_clinical_decision(self, uow: UnitOfWork) -> RecordClinicalDecisionHandler:
        return RecordClinicalDecisionHandler(
            uow.qasets, self._base_language(uow), self._recorder(uow)
        )

    def build_record_translation_decision(
        self, uow: UnitOfWork
    ) -> RecordTranslationDecisionHandler:
        return RecordTranslationDecisionHandler(
            uow.qasets, self._base_language(uow), self._recorder(uow)
        )

    def build_record_audio_decision(self, uow: UnitOfWork) -> RecordAudioDecisionHandler:
        return RecordAudioDecisionHandler(uow.qasets, self._recorder(uow))

    def build_get_clinical_validation(self, uow: UnitOfWork) -> GetClinicalValidationHandler:
        return GetClinicalValidationHandler(uow.qasets, self._recorder(uow))

    def build_get_translation_validation(self, uow: UnitOfWork) -> GetTranslationValidationHandler:
        return GetTranslationValidationHandler(uow.qasets, self._recorder(uow))

    def build_get_audio_validation(self, uow: UnitOfWork) -> GetAudioValidationHandler:
        return GetAudioValidationHandler(uow.qasets, self._recorder(uow))

    def build_list_prompt_templates(self, uow: UnitOfWork) -> ListPromptTemplatesHandler:
        return ListPromptTemplatesHandler(uow.prompt_templates, uow.users)

    def build_get_prompt_template(self, uow: UnitOfWork) -> GetPromptTemplateHandler:
        return GetPromptTemplateHandler(uow.prompt_templates, uow.users)

    def build_update_prompt_template(self, uow: UnitOfWork) -> UpdatePromptTemplateHandler:
        return UpdatePromptTemplateHandler(uow.prompt_templates, uow.users, self._clock)

    def build_seed_prompt_templates(self, uow: UnitOfWork) -> SeedPromptTemplatesHandler:
        return SeedPromptTemplatesHandler(uow.prompt_templates, self._clock)

    def build_translate_answer(self, uow: UnitOfWork) -> TranslateAnswerHandler:
        return TranslateAnswerHandler(
            uow.qasets,
            uow.languages,
            self._translators(uow),
            self._views(uow),
            self._resetter(uow),
        )

    def build_translate_variant(self, uow: UnitOfWork) -> TranslateVariantHandler:
        return TranslateVariantHandler(
            uow.qasets,
            uow.languages,
            self._translators(uow),
            self._views(uow),
            self._resetter(uow),
        )
