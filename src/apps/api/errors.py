from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from qa_authoring.application.language_errors import (
    LanguageCodeAlreadyExistsError,
    LanguageNotFoundError,
)
from qa_authoring.domain.model.language import InvalidLanguageNameError
from qa_authoring.domain.value_objects.language_code import InvalidLanguageCodeError

if TYPE_CHECKING:
    from fastapi import FastAPI, Request


@dataclass(frozen=True, slots=True)
class _Rule:
    status: int
    code: str


# Every domain/application error a client can receive, mapped to an HTTP status and a stable
# machine code. An unmapped error is a 500.
_RULES: dict[type[Exception], _Rule] = {
    LanguageNotFoundError: _Rule(404, "language_not_found"),
    LanguageCodeAlreadyExistsError: _Rule(409, "language_code_already_exists"),
    InvalidLanguageCodeError: _Rule(422, "invalid_language_code"),
    InvalidLanguageNameError: _Rule(422, "invalid_language_name"),
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
    if rule is None or rule.status >= 500:
        return JSONResponse(
            status_code=500, content=_body("internal_error", "an internal error occurred", None)
        )
    return JSONResponse(status_code=rule.status, content=_body(rule.code, str(exc), None))


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
