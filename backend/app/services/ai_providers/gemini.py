import json
import ssl
from socket import timeout as SocketTimeout
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import certifi
from pydantic import BaseModel, ValidationError

from app.services.ai_client import (
    AIErrorCategory,
    AIMessage,
    AIProviderError,
    AITimeoutError,
    InvalidStructuredOutputError,
    MalformedModelResponseError,
    MissingAIAPIKeyError,
    StructuredModel,
)


class GeminiAIClient:
    provider_name = "gemini"

    def __init__(
        self, api_key: str | None, model: str, timeout_seconds: float
    ) -> None:
        if not api_key:
            raise MissingAIAPIKeyError("GEMINI_API_KEY is required for Gemini.")

        self._api_key = api_key
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._ssl_context = ssl.create_default_context(cafile=certifi.where())

    @property
    def model_name(self) -> str:
        return self._model

    def generate_text(self, prompt: str, system: str | None = None) -> str:
        payload = self._payload([AIMessage(role="user", content=prompt)], system)
        response = self._post_generate_content(payload)
        return self._extract_text(response)

    def generate_structured(
        self,
        prompt: str,
        output_schema: type[StructuredModel],
        system: str | None = None,
    ) -> StructuredModel:
        payload = self._payload([AIMessage(role="user", content=prompt)], system)
        payload["generationConfig"] = {
            "responseMimeType": "application/json",
            "responseJsonSchema": output_schema.model_json_schema(),
        }
        response = self._post_generate_content(payload)
        text = self._extract_text(response)

        try:
            return output_schema.model_validate_json(text)
        except ValidationError as exc:
            raise InvalidStructuredOutputError(
                "Gemini returned structured output that failed validation."
            ) from exc

    def chat(self, messages: list[AIMessage], system: str | None = None) -> str:
        payload = self._payload(messages, system)
        response = self._post_generate_content(payload)
        return self._extract_text(response)

    def _payload(
        self, messages: list[AIMessage], system: str | None
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "contents": [
                {
                    "role": self._gemini_role(message.role),
                    "parts": [{"text": message.content}],
                }
                for message in messages
            ]
        }
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}
        return payload

    def _post_generate_content(self, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        request = Request(
            self._endpoint(),
            data=body,
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": self._api_key,
            },
            method="POST",
        )

        try:
            with urlopen(
                request,
                timeout=self._timeout_seconds,
                context=self._ssl_context,
            ) as response:
                return self._decode_json(response.read())
        except TimeoutError as exc:
            raise AITimeoutError(
                "Gemini request timed out.",
                provider=self.provider_name,
                model=self._model,
            ) from exc
        except SocketTimeout as exc:
            raise AITimeoutError(
                "Gemini request timed out.",
                provider=self.provider_name,
                model=self._model,
            ) from exc
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            category = self._classify_http_error(exc.code, detail)
            raise AIProviderError(
                self._provider_error_message(exc.code, detail),
                category=category,
                provider=self.provider_name,
                model=self._model,
                status_code=exc.code,
                retryable=category
                in {
                    AIErrorCategory.RATE_LIMIT,
                    AIErrorCategory.QUOTA_EXHAUSTED,
                    AIErrorCategory.UNAVAILABLE,
                    AIErrorCategory.PROVIDER_5XX,
                },
            ) from exc
        except URLError as exc:
            raise AIProviderError(
                f"Gemini request failed: {exc.reason}",
                category=AIErrorCategory.NETWORK_ERROR,
                provider=self.provider_name,
                model=self._model,
                retryable=True,
            ) from exc

    def _endpoint(self) -> str:
        return (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self._model}:generateContent"
        )

    def _decode_json(self, raw_body: bytes) -> dict[str, Any]:
        try:
            decoded = json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise MalformedModelResponseError(
                "Gemini returned a non-JSON response."
            ) from exc

        if not isinstance(decoded, dict):
            raise MalformedModelResponseError("Gemini response was not an object.")
        return decoded

    def _extract_text(self, response: dict[str, Any]) -> str:
        try:
            text = response["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError) as exc:
            raise MalformedModelResponseError(
                "Gemini response did not include candidate text."
            ) from exc

        if not isinstance(text, str) or not text.strip():
            raise MalformedModelResponseError("Gemini candidate text was empty.")
        return text

    def _provider_error_message(self, status_code: int, detail: str) -> str:
        safe_detail = self._safe_detail(detail)
        if safe_detail:
            return f"Gemini request failed with HTTP {status_code}: {safe_detail}"
        return f"Gemini request failed with HTTP {status_code}."

    def _classify_http_error(self, status_code: int, detail: str) -> AIErrorCategory:
        lowered = detail.lower()
        if status_code in {401, 403}:
            return AIErrorCategory.AUTHENTICATION
        if status_code == 400:
            return AIErrorCategory.INVALID_REQUEST
        if status_code == 429:
            if any(term in lowered for term in ("quota", "resource_exhausted")):
                return AIErrorCategory.QUOTA_EXHAUSTED
            return AIErrorCategory.RATE_LIMIT
        if status_code == 503:
            return AIErrorCategory.UNAVAILABLE
        if 500 <= status_code <= 599:
            return AIErrorCategory.PROVIDER_5XX
        return AIErrorCategory.UNKNOWN_PROVIDER_ERROR

    def _safe_detail(self, detail: str) -> str:
        if detail:
            try:
                parsed = json.loads(detail)
            except json.JSONDecodeError:
                return detail[:500]
            error = parsed.get("error", {})
            if isinstance(error, str):
                return error[:500]
            if not isinstance(error, dict):
                return ""
            message = error.get("message")
            status = error.get("status")
            if message and status:
                return f"{status}: {message}"[:500]
            if message:
                return str(message)[:500]
        return ""

    def _gemini_role(self, role: str) -> str:
        if role == "assistant":
            return "model"
        if role in {"user", "model"}:
            return role
        return "user"
