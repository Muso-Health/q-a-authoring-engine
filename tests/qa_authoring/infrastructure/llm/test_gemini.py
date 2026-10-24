from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest
from google.genai import errors

from qa_authoring.application.ports.llm import LlmUnavailableError
from qa_authoring.infrastructure.llm.gemini import GeminiLlm


class FakeModels:
    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []
        self.reply: str | None = "  answer  "
        self.error: Exception | None = None
        self.delay = 0.0

    async def generate_content(self, **request: Any) -> Any:
        self.requests.append(request)
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.error is not None:
            raise self.error
        return SimpleNamespace(text=self.reply)


class FakeClient:
    def __init__(self) -> None:
        self.models = FakeModels()
        self.aio = SimpleNamespace(models=self.models)


def _gemini(client: FakeClient, **overrides: Any) -> GeminiLlm:
    settings: dict[str, Any] = {
        "model": "gemini-2.5-flash",
        "project": "proj",
        "location": "europe-west1",
        "api_key": "",
        "timeout_seconds": 1.0,
        "client_factory": lambda: client,
    }
    settings.update(overrides)
    return GeminiLlm(**settings)


async def test_generate_sends_the_prompt_to_the_configured_model() -> None:
    client = FakeClient()

    text = await _gemini(client).generate("Translate this.")

    assert text == "answer"
    [request] = client.models.requests
    assert (request["model"], request["contents"]) == ("gemini-2.5-flash", "Translate this.")


@pytest.mark.parametrize(
    "error",
    [
        errors.ServerError(503, {"error": {"message": "overloaded", "status": "UNAVAILABLE"}}),
        errors.ClientError(429, {"error": {"message": "quota", "status": "RESOURCE_EXHAUSTED"}}),
    ],
)
async def test_api_errors_become_unavailable(error: Exception) -> None:
    client = FakeClient()
    client.models.error = error
    with pytest.raises(LlmUnavailableError):
        await _gemini(client).generate("x")


async def test_a_timeout_becomes_unavailable() -> None:
    client = FakeClient()
    client.models.delay = 0.5
    with pytest.raises(LlmUnavailableError, match="timed out"):
        await _gemini(client, timeout_seconds=0.05).generate("x")


@pytest.mark.parametrize("reply", [None, "", "   "])
async def test_an_empty_reply_is_unavailable(reply: str | None) -> None:
    client = FakeClient()
    client.models.reply = reply
    with pytest.raises(LlmUnavailableError):
        await _gemini(client).generate("x")


async def test_it_needs_a_project_or_an_api_key() -> None:
    client = FakeClient()
    with pytest.raises(LlmUnavailableError, match="not configured"):
        await _gemini(client, project="", api_key="").generate("x")
    assert await _gemini(client, project="", api_key="key").generate("x") == "answer"
