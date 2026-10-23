from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from collections.abc import Sequence

    from qa_authoring.application.intent_response import IntentResult


class RegisterIntentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str


class IntentResponse(BaseModel):
    id: UUID
    text: str

    @classmethod
    def of(cls, result: IntentResult) -> IntentResponse:
        return cls(id=result.id, text=result.text)


class IntentsResponse(BaseModel):
    items: list[IntentResponse]

    @classmethod
    def of(cls, results: Sequence[IntentResult]) -> IntentsResponse:
        return cls(items=[IntentResponse.of(result) for result in results])
