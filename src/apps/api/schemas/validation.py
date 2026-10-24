from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from qa_authoring.application.validation_response import ValidationResult
    from qa_authoring.domain.model.validation import ValidationState


class DecisionRequest(BaseModel):
    """``decision`` is ``validated`` or ``rejected`` (422 ``invalid_decision`` otherwise)."""

    model_config = ConfigDict(extra="forbid")

    decision: str
    note: str | None = None


class ValidationStateResponse(BaseModel):
    """A current validation state, as shown inside a QA set (``null`` when pending)."""

    state: str

    @classmethod
    def of(cls, state: ValidationState | None) -> ValidationStateResponse | None:
        return None if state is None else cls(state=state.value)


class ValidationEventResponse(BaseModel):
    from_state: str | None
    to_state: str
    note: str | None
    actor_email: str
    occurred_at: datetime


class ValidationResponse(BaseModel):
    """The current state (``pending`` until the first decision) and the full history."""

    kind: str
    state: str
    history: list[ValidationEventResponse]

    @classmethod
    def of(cls, result: ValidationResult) -> ValidationResponse:
        return cls(
            kind=result.kind,
            state=result.state,
            history=[
                ValidationEventResponse(
                    from_state=e.from_state,
                    to_state=e.to_state,
                    note=e.note,
                    actor_email=e.actor_email,
                    occurred_at=e.occurred_at,
                )
                for e in result.history
            ],
        )
