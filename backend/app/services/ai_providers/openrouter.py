import json
import logging
import ssl
from socket import timeout as SocketTimeout
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import certifi
from pydantic import ValidationError

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


OPENROUTER_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
logger = logging.getLogger(__name__)


class OpenRouterAIClient:
    provider_name = "openrouter"

    def __init__(
        self,
        *,
        api_key: str | None,
        models: list[str],
        timeout_seconds: float,
        free_only: bool,
        free_model_allowlist: set[str],
        site_url: str | None = None,
        app_name: str | None = None,
    ) -> None:
        if not api_key:
            raise MissingAIAPIKeyError("OPENROUTER_API_KEY is required for OpenRouter.")
        if not models:
            raise AIProviderError(
                "OPENROUTER_MODEL is required for OpenRouter fallback.",
                category=AIErrorCategory.CONFIGURATION,
                provider=self.provider_name,
            )
        if free_only:
            unapproved = [model for model in models if model not in free_model_allowlist]
            if unapproved or not free_model_allowlist:
                raise AIProviderError(
                    "OpenRouter free-only mode rejected non-allowlisted models.",
                    category=AIErrorCategory.CONFIGURATION,
                    provider=self.provider_name,
                    model=", ".join(unapproved or models),
                )

        self._api_key = api_key
        self._models = models
        self._timeout_seconds = timeout_seconds
        self._site_url = site_url
        self._app_name = app_name
        self._last_model_attempted = models[0]
        self._ssl_context = ssl.create_default_context(cafile=certifi.where())

    @property
    def model_name(self) -> str:
        return self._last_model_attempted

    def generate_text(self, prompt: str, system: str | None = None) -> str:
        response = self._chat_completion(
            [AIMessage(role="user", content=prompt)],
            system=system,
            structured=False,
        )
        return self._extract_text(response)

    def generate_structured(
        self,
        prompt: str,
        output_schema: type[StructuredModel],
        system: str | None = None,
    ) -> StructuredModel:
        response_format = self._structured_response_format(output_schema)
        messages = [AIMessage(role="user", content=prompt)]
        last_error: (
            AIProviderError
            | AITimeoutError
            | InvalidStructuredOutputError
            | MalformedModelResponseError
            | None
        ) = None
        for index, model in enumerate(self._models):
            self._last_model_attempted = model
            will_attempt_another = index < len(self._models) - 1
            payload = self._payload(
                model,
                messages,
                system,
                response_format=response_format,
                require_parameters=True,
            )
            try:
                response = self._post_chat_completion(payload)
                text = self._extract_text(response)
                try:
                    parsed = json.loads(text)
                except json.JSONDecodeError as exc:
                    raise MalformedModelResponseError(
                        "OpenRouter returned malformed structured JSON."
                    ) from exc
                try:
                    return output_schema.model_validate(parsed)
                except ValidationError as exc:
                    raise InvalidStructuredOutputError(
                        "OpenRouter returned structured output that failed validation."
                    ) from exc
            except (AIProviderError, AITimeoutError) as exc:
                last_error = exc
                category = getattr(exc, "category", None)
                if category not in {
                    AIErrorCategory.RATE_LIMIT,
                    AIErrorCategory.QUOTA_EXHAUSTED,
                    AIErrorCategory.UNAVAILABLE,
                    AIErrorCategory.TIMEOUT,
                    AIErrorCategory.NETWORK_ERROR,
                    AIErrorCategory.PROVIDER_5XX,
                }:
                    raise
                if will_attempt_another:
                    continue
                break
            except (InvalidStructuredOutputError, MalformedModelResponseError) as exc:
                last_error = exc
                self._log_structured_model_failure(
                    model=model,
                    failure_category=self._structured_failure_category(exc),
                    will_attempt_another=will_attempt_another,
                )
                if will_attempt_another:
                    continue
                break
        assert last_error is not None
        raise last_error

    def chat(self, messages: list[AIMessage], system: str | None = None) -> str:
        response = self._chat_completion(messages, system=system, structured=False)
        return self._extract_text(response)

    def _chat_completion(
        self,
        messages: list[AIMessage],
        *,
        system: str | None,
        structured: bool,
    ) -> dict[str, Any]:
        last_error: AIProviderError | AITimeoutError | None = None
        for model in self._models:
            self._last_model_attempted = model
            payload = self._payload(
                model,
                messages,
                system,
                response_format={"type": "json_object"} if structured else None,
            )
            try:
                return self._post_chat_completion(payload)
            except (AIProviderError, AITimeoutError) as exc:
                last_error = exc
                category = getattr(exc, "category", None)
                if category not in {
                    AIErrorCategory.RATE_LIMIT,
                    AIErrorCategory.QUOTA_EXHAUSTED,
                    AIErrorCategory.UNAVAILABLE,
                    AIErrorCategory.TIMEOUT,
                    AIErrorCategory.NETWORK_ERROR,
                    AIErrorCategory.PROVIDER_5XX,
                }:
                    raise
        assert last_error is not None
        raise last_error

    def _payload(
        self,
        model: str,
        messages: list[AIMessage],
        system: str | None,
        *,
        response_format: dict[str, Any] | None = None,
        require_parameters: bool = False,
    ) -> dict[str, Any]:
        openrouter_messages = []
        if system:
            openrouter_messages.append({"role": "system", "content": system})
        openrouter_messages.extend(
            {"role": self._chat_role(message.role), "content": message.content}
            for message in messages
        )
        payload: dict[str, Any] = {
            "model": model,
            "messages": openrouter_messages,
        }
        if response_format is not None:
            payload["response_format"] = response_format
        if require_parameters:
            payload["provider"] = {"require_parameters": True}
        return payload

    def _structured_response_format(
        self, output_schema: type[StructuredModel]
    ) -> dict[str, Any]:
        return {
            "type": "json_schema",
            "json_schema": {
                "name": output_schema.__name__,
                "strict": True,
                "schema": output_schema.model_json_schema(),
            },
        }

    def _post_chat_completion(self, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        if self._site_url:
            headers["HTTP-Referer"] = self._site_url
        if self._app_name:
            headers["X-Title"] = self._app_name
        request = Request(
            OPENROUTER_ENDPOINT,
            data=body,
            headers=headers,
            method="POST",
        )
        model = str(payload.get("model") or self.model_name)
        try:
            with urlopen(
                request,
                timeout=self._timeout_seconds,
                context=self._ssl_context,
            ) as response:
                return self._decode_json(response.read())
        except TimeoutError as exc:
            raise AITimeoutError(
                "OpenRouter request timed out.",
                provider=self.provider_name,
                model=model,
            ) from exc
        except SocketTimeout as exc:
            raise AITimeoutError(
                "OpenRouter request timed out.",
                provider=self.provider_name,
                model=model,
            ) from exc
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            category = self._classify_http_error(exc.code, detail)
            raise AIProviderError(
                self._provider_error_message(exc.code, detail),
                category=category,
                provider=self.provider_name,
                model=model,
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
                f"OpenRouter request failed: {exc.reason}",
                category=AIErrorCategory.NETWORK_ERROR,
                provider=self.provider_name,
                model=model,
                retryable=True,
            ) from exc

    def _decode_json(self, raw_body: bytes) -> dict[str, Any]:
        try:
            decoded = json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise MalformedModelResponseError(
                "OpenRouter returned a non-JSON response."
            ) from exc
        if not isinstance(decoded, dict):
            raise MalformedModelResponseError("OpenRouter response was not an object.")
        return decoded

    def _extract_text(self, response: dict[str, Any]) -> str:
        try:
            content = response["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise MalformedModelResponseError(
                "OpenRouter response did not include message content."
            ) from exc
        if not isinstance(content, str) or not content.strip():
            raise MalformedModelResponseError("OpenRouter message content was empty.")
        return content

    def _provider_error_message(self, status_code: int, detail: str) -> str:
        safe_detail = self._safe_detail(detail)
        if safe_detail:
            return f"OpenRouter request failed with HTTP {status_code}: {safe_detail}"
        return f"OpenRouter request failed with HTTP {status_code}."

    def _classify_http_error(self, status_code: int, detail: str) -> AIErrorCategory:
        lowered = detail.lower()
        if status_code in {401, 403}:
            return AIErrorCategory.AUTHENTICATION
        if status_code == 400:
            return AIErrorCategory.INVALID_REQUEST
        if status_code == 429:
            if any(term in lowered for term in ("quota", "insufficient", "credits")):
                return AIErrorCategory.QUOTA_EXHAUSTED
            return AIErrorCategory.RATE_LIMIT
        if status_code == 503:
            return AIErrorCategory.UNAVAILABLE
        if 500 <= status_code <= 599:
            return AIErrorCategory.PROVIDER_5XX
        return AIErrorCategory.UNKNOWN_PROVIDER_ERROR

    def _safe_detail(self, detail: str) -> str:
        if not detail:
            return ""
        try:
            parsed = json.loads(detail)
        except json.JSONDecodeError:
            return detail[:500]
        error = parsed.get("error")
        if isinstance(error, dict):
            message = error.get("message")
            if message:
                return str(message)[:500]
        if isinstance(error, str):
            return error[:500]
        return ""

    def _chat_role(self, role: str) -> str:
        if role in {"system", "user", "assistant"}:
            return role
        if role == "model":
            return "assistant"
        return "user"

    def _structured_failure_category(
        self, error: InvalidStructuredOutputError | MalformedModelResponseError
    ) -> str:
        if isinstance(error, InvalidStructuredOutputError):
            return "pydantic_validation_failed"
        return "malformed_or_empty_content"

    def _log_structured_model_failure(
        self,
        *,
        model: str,
        failure_category: str,
        will_attempt_another: bool,
    ) -> None:
        fields = {
            "provider": self.provider_name,
            "requested_model": model,
            "failure_category": failure_category,
            "will_attempt_another_model": will_attempt_another,
        }
        logger.info(
            "openrouter_structured_model_failure %s",
            fields,
            extra={"ai": fields},
        )


def create_openrouter_client(settings) -> OpenRouterAIClient | None:  # type: ignore[no-untyped-def]
    models = [
        model
        for model in (settings.openrouter_model, *settings.openrouter_fallback_models)
        if model
    ]
    if not settings.openrouter_api_key or not models:
        return None
    return OpenRouterAIClient(
        api_key=settings.openrouter_api_key,
        models=models,
        timeout_seconds=settings.ai_timeout_seconds,
        free_only=settings.ai_free_only,
        free_model_allowlist=set(settings.openrouter_free_models),
        site_url=settings.openrouter_site_url,
        app_name=settings.openrouter_app_name,
    )
