from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from qa_authoring.application.ports.llm import LlmUnavailableError

if TYPE_CHECKING:
    from collections.abc import Callable


class GeminiLlm:
    """The LLM port on Google Gemini, through Vertex AI (``project`` / ``location``, Application
    Default Credentials) or, when ``api_key`` is set, the Gemini API. The SDK client is built
    lazily, so the app starts without credentials; the call is bounded by ``timeout_seconds``."""

    def __init__(
        self,
        *,
        model: str,
        project: str,
        location: str,
        api_key: str,
        timeout_seconds: float,
        client_factory: Callable[[], Any] | None = None,
    ) -> None:
        self._model = model
        self._project = project
        self._location = location
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds
        self._client_factory = client_factory or self._default_client
        self._client: Any = None

    async def generate(self, prompt: str) -> str:
        from google.genai import errors

        if not self._project and not self._api_key:
            raise LlmUnavailableError("the Gemini model is not configured")
        if self._client is None:
            self._client = self._client_factory()
        try:
            response = await asyncio.wait_for(
                self._client.aio.models.generate_content(model=self._model, contents=prompt),
                self._timeout_seconds,
            )
        except TimeoutError as exc:
            raise LlmUnavailableError("the Gemini model timed out") from exc
        except errors.APIError as exc:
            raise LlmUnavailableError("the Gemini model refused or failed the request") from exc
        text = (response.text or "").strip()
        if not text:
            raise LlmUnavailableError("the Gemini model returned an empty answer")
        return text

    def _default_client(self) -> Any:
        from google import genai

        if self._api_key:
            return genai.Client(api_key=self._api_key)
        return genai.Client(vertexai=True, project=self._project, location=self._location)
