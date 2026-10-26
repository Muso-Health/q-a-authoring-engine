from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from qa_authoring.application.access_errors import PermissionDeniedError
from qa_authoring.application.audio_errors import (
    AudioNotFoundError,
    AudioTooLargeError,
    UnsupportedAudioTypeError,
)
from qa_authoring.application.category_errors import CategoryInUseError, CategoryNotFoundError
from qa_authoring.application.completeness_errors import NoDocumentationError
from qa_authoring.application.documentation_errors import (
    DocumentationNotFoundError,
    DocumentTooLargeError,
    UnsupportedDocumentTypeError,
)
from qa_authoring.application.export_errors import NothingToExportError
from qa_authoring.application.intent_errors import IntentInUseError, IntentNotFoundError
from qa_authoring.application.language_errors import (
    LanguageCodeAlreadyExistsError,
    LanguageInUseError,
    LanguageNotFoundError,
)
from qa_authoring.application.ports.completeness_analyzer import CompletenessEngineError
from qa_authoring.application.ports.identity import UnauthenticatedError
from qa_authoring.application.ports.translator import (
    TranslationEngineError,
    UnsupportedLanguageForEngineError,
)
from qa_authoring.application.ports.variant_generator import GenerationEngineError
from qa_authoring.application.project_errors import (
    ProjectHasProtocolsError,
    ProjectNotFoundError,
    UnknownBaseLanguageError,
)
from qa_authoring.application.prompt_template_errors import PromptTemplateNotFoundError
from qa_authoring.application.protocol_errors import (
    ProtocolHasThemesError,
    ProtocolNotFoundError,
)
from qa_authoring.application.qaset_errors import QASetNotFoundError, UnknownLanguageError
from qa_authoring.application.role_errors import (
    RoleInUseError,
    RoleNameExistsError,
    RoleNotFoundError,
)
from qa_authoring.application.theme_errors import ThemeHasQASetsError, ThemeNotFoundError
from qa_authoring.application.translation_engines import UnknownEngineError
from qa_authoring.application.user_errors import (
    AssignmentNotFoundError,
    EmailAlreadyExistsError,
    NotProvisionedError,
    UserNotFoundError,
)
from qa_authoring.application.validation_errors import (
    NoBaseLanguagePresenceError,
    NotATranslationError,
)
from qa_authoring.application.validation_queues import InvalidQueueFilterError
from qa_authoring.domain.model.language import InvalidLanguageNameError
from qa_authoring.domain.model.permission import UnknownPermissionError
from qa_authoring.domain.model.prompt_template import InvalidPromptTemplateError
from qa_authoring.domain.model.qaset import (
    AnswerNotFoundError,
    CategoryNotAttachedError,
    IntentNotAttachedError,
    LanguageAlreadyPresentError,
    LanguageNotPresentError,
    LanguagePresenceRequiredError,
    LinkAlreadyExistsError,
    NoAudioError,
    QuestionVariantNotFoundError,
    SameLanguageError,
    SelfLinkError,
    TranslationLinkNotFoundError,
)
from qa_authoring.domain.model.user import InvalidEmailError
from qa_authoring.domain.model.validation import InvalidDecisionError
from qa_authoring.domain.value_objects.language_code import InvalidLanguageCodeError
from qa_authoring.domain.value_objects.naming import InvalidNameError, InvalidTextError

if TYPE_CHECKING:
    from collections.abc import Callable

    from fastapi import FastAPI, Request


@dataclass(frozen=True, slots=True)
class _Rule:
    status: int
    code: str
    details: Callable[[Any], dict[str, Any]] | None = None


def _prompt_template_details(exc: InvalidPromptTemplateError) -> dict[str, Any]:
    # The offending placeholders reach the client so the editor can show what to fix.
    return {"missing": list(exc.missing), "unknown": list(exc.unknown)}


# Every domain/application error a client can receive, mapped to an HTTP status and a stable
# machine code. An unmapped error is a 500.
_RULES: dict[type[Exception], _Rule] = {
    UnauthenticatedError: _Rule(401, "unauthenticated"),
    NotProvisionedError: _Rule(403, "not_provisioned"),
    PermissionDeniedError: _Rule(403, "permission_denied"),
    UserNotFoundError: _Rule(404, "user_not_found"),
    RoleNotFoundError: _Rule(404, "role_not_found"),
    AssignmentNotFoundError: _Rule(404, "assignment_not_found"),
    PromptTemplateNotFoundError: _Rule(404, "prompt_template_not_found"),
    DocumentationNotFoundError: _Rule(404, "documentation_not_found"),
    NoDocumentationError: _Rule(409, "no_documentation"),
    NothingToExportError: _Rule(409, "nothing_to_export"),
    UnsupportedDocumentTypeError: _Rule(422, "unsupported_document_type"),
    DocumentTooLargeError: _Rule(422, "document_too_large"),
    CompletenessEngineError: _Rule(502, "completeness_engine_error"),
    RoleInUseError: _Rule(409, "role_in_use"),
    EmailAlreadyExistsError: _Rule(409, "email_already_exists"),
    RoleNameExistsError: _Rule(409, "role_name_exists"),
    NoBaseLanguagePresenceError: _Rule(409, "no_base_language_presence"),
    NotATranslationError: _Rule(422, "not_a_translation"),
    InvalidDecisionError: _Rule(422, "invalid_decision"),
    InvalidQueueFilterError: _Rule(422, "invalid_queue_filter"),
    UnknownEngineError: _Rule(422, "unknown_engine"),
    UnsupportedLanguageForEngineError: _Rule(422, "unsupported_language_for_engine"),
    TranslationEngineError: _Rule(502, "translation_engine_error"),
    GenerationEngineError: _Rule(502, "generation_engine_error"),
    InvalidPromptTemplateError: _Rule(422, "invalid_prompt_template", _prompt_template_details),
    UnknownPermissionError: _Rule(422, "unknown_permission"),
    InvalidEmailError: _Rule(422, "invalid_email"),
    LanguageNotFoundError: _Rule(404, "language_not_found"),
    ProjectNotFoundError: _Rule(404, "project_not_found"),
    ProtocolNotFoundError: _Rule(404, "protocol_not_found"),
    ThemeNotFoundError: _Rule(404, "theme_not_found"),
    QASetNotFoundError: _Rule(404, "qaset_not_found"),
    LanguageNotPresentError: _Rule(404, "language_not_present"),
    QuestionVariantNotFoundError: _Rule(404, "variant_not_found"),
    AnswerNotFoundError: _Rule(404, "answer_not_found"),
    TranslationLinkNotFoundError: _Rule(404, "link_not_found"),
    IntentNotFoundError: _Rule(404, "intent_not_found"),
    IntentNotAttachedError: _Rule(404, "intent_not_attached"),
    CategoryNotFoundError: _Rule(404, "category_not_found"),
    CategoryNotAttachedError: _Rule(404, "category_not_attached"),
    AudioNotFoundError: _Rule(404, "audio_not_found"),
    NoAudioError: _Rule(404, "audio_not_found"),
    LanguageCodeAlreadyExistsError: _Rule(409, "language_code_already_exists"),
    LanguageInUseError: _Rule(409, "language_in_use"),
    ProjectHasProtocolsError: _Rule(409, "project_has_protocols"),
    ProtocolHasThemesError: _Rule(409, "protocol_has_themes"),
    ThemeHasQASetsError: _Rule(409, "theme_has_qasets"),
    LanguageAlreadyPresentError: _Rule(409, "language_already_present"),
    LanguagePresenceRequiredError: _Rule(409, "language_presence_required"),
    LinkAlreadyExistsError: _Rule(409, "link_already_exists"),
    IntentInUseError: _Rule(409, "intent_in_use"),
    CategoryInUseError: _Rule(409, "category_in_use"),
    InvalidLanguageCodeError: _Rule(422, "invalid_language_code"),
    InvalidLanguageNameError: _Rule(422, "invalid_language_name"),
    InvalidNameError: _Rule(422, "invalid_name"),
    UnknownBaseLanguageError: _Rule(422, "unknown_base_language"),
    InvalidTextError: _Rule(422, "invalid_text"),
    UnknownLanguageError: _Rule(422, "unknown_language"),
    SameLanguageError: _Rule(422, "same_language"),
    SelfLinkError: _Rule(422, "self_link"),
    UnsupportedAudioTypeError: _Rule(422, "unsupported_audio_type"),
    AudioTooLargeError: _Rule(422, "audio_too_large"),
}

_VALIDATION_CODE = "invalid_request"
_VALIDATION_STATUS = 422


def _rule_for(exc_type: type) -> _Rule | None:
    for klass in exc_type.__mro__:
        if klass in _RULES:
            return _RULES[klass]
    return None


def _body(code: str, message: str, details: dict[str, Any] | None) -> dict[str, Any]:
    # One shape for every failure: a machine code, a human message, optional structured details.
    return {"code": code, "message": message, "details": details}


async def _handle(request: Request, exc: Exception) -> JSONResponse:
    rule = _rule_for(type(exc))
    if rule is None:
        return JSONResponse(
            status_code=500, content=_body("internal_error", "an internal error occurred", None)
        )
    # Mapped errors carry messages written by this application, never provider internals.
    details = None if rule.details is None else rule.details(exc)
    return JSONResponse(status_code=rule.status, content=_body(rule.code, str(exc), details))


async def _handle_validation(request: Request, exc: Exception) -> JSONResponse:
    validation = cast("RequestValidationError", exc)
    return JSONResponse(
        status_code=_VALIDATION_STATUS,
        content=_body(
            _VALIDATION_CODE,
            "the request is malformed",
            {"errors": jsonable_encoder(validation.errors())},
        ),
    )


async def _handle_http_exception(request: Request, exc: Exception) -> JSONResponse:
    http = cast("HTTPException", exc)
    return JSONResponse(
        status_code=http.status_code,
        content=_body(f"http_{http.status_code}", str(http.detail), None),
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(RequestValidationError, _handle_validation)
    app.add_exception_handler(HTTPException, _handle_http_exception)
    for error_type in _RULES:
        app.add_exception_handler(error_type, _handle)
    app.add_exception_handler(Exception, _handle)
