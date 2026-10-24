from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from qa_authoring.application.generate_variants.command import GeneratedVariantsResult


class GenerateVariantsRequest(BaseModel):
    """Free-text guidance for the model (audience, situation...); may be empty."""

    model_config = ConfigDict(extra="forbid")

    context: str = ""


class GeneratedVariantsResponse(BaseModel):
    candidates: list[str]

    @classmethod
    def of(cls, result: GeneratedVariantsResult) -> GeneratedVariantsResponse:
        return cls(candidates=list(result.candidates))
