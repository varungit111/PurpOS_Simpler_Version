import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, TypeVar

from pydantic import BaseModel

from app.config.settings import settings


StructuredModel = TypeVar("StructuredModel", bound=BaseModel)


class AIClientError(Exception):
    pass


class MissingAIAPIKeyError(AIClientError):
    pass


class AIProviderError(AIClientError):
    def __init__(
        self,
        message: str,
        *,
        category: "AIErrorCategory | None" = None,
        provider: str | None = None,
        model: str | None = None,
        status_code: int | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.category = category or AIErrorCategory.UNKNOWN_PROVIDER_ERROR
        self.provider = provider
        self.model = model
        self.status_code = status_code
        self.retryable = retryable


class AITimeoutError(AIClientError):
    def __init__(
        self,
        message: str,
        *,
        provider: str | None = None,
        model: str | None = None,
        retryable: bool = True,
    ) -> None:
        super().__init__(message)
        self.category = AIErrorCategory.TIMEOUT
        self.provider = provider
        self.model = model
        self.retryable = retryable


class InvalidStructuredOutputError(AIClientError):
    pass


class MalformedModelResponseError(AIClientError):
    pass


class AIErrorCategory(StrEnum):
    RATE_LIMIT = "rate_limit"
    QUOTA_EXHAUSTED = "quota_exhausted"
    UNAVAILABLE = "unavailable"
    TIMEOUT = "timeout"
    NETWORK_ERROR = "network_error"
    PROVIDER_5XX = "provider_5xx"
    AUTHENTICATION = "authentication"
    CONFIGURATION = "configuration"
    INVALID_REQUEST = "invalid_request"
    STRUCTURED_OUTPUT_ERROR = "structured_output_error"
    UNKNOWN_PROVIDER_ERROR = "unknown_provider_error"


class AIMessage(BaseModel):
    role: str
    content: str


class AIClient(Protocol):
    def generate_text(self, prompt: str, system: str | None = None) -> str:
        raise NotImplementedError

    def generate_structured(
        self,
        prompt: str,
        output_schema: type[StructuredModel],
        system: str | None = None,
    ) -> StructuredModel:
        raise NotImplementedError

    def chat(self, messages: list[AIMessage], system: str | None = None) -> str:
        raise NotImplementedError


FALLBACK_ELIGIBLE_CATEGORIES = {
    AIErrorCategory.RATE_LIMIT,
    AIErrorCategory.QUOTA_EXHAUSTED,
    AIErrorCategory.UNAVAILABLE,
    AIErrorCategory.TIMEOUT,
    AIErrorCategory.NETWORK_ERROR,
    AIErrorCategory.PROVIDER_5XX,
}

RETRY_ELIGIBLE_CATEGORIES = {
    AIErrorCategory.UNAVAILABLE,
    AIErrorCategory.TIMEOUT,
    AIErrorCategory.NETWORK_ERROR,
    AIErrorCategory.PROVIDER_5XX,
}

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RetryPolicy:
    max_retries: int = 1
    backoff_seconds: float = 0.25
    sleeper: Callable[[float], None] = time.sleep


class FallbackAIClient:
    def __init__(
        self,
        *,
        primary: AIClient,
        secondary: AIClient | None,
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        self._primary = primary
        self._secondary = secondary
        self._retry_policy = retry_policy or RetryPolicy()

    def generate_text(self, prompt: str, system: str | None = None) -> str:
        return self._run("generate_text", lambda client: client.generate_text(prompt, system))

    def generate_structured(
        self,
        prompt: str,
        output_schema: type[StructuredModel],
        system: str | None = None,
    ) -> StructuredModel:
        return self._run(
            "generate_structured",
            lambda client: client.generate_structured(prompt, output_schema, system),
        )

    def chat(self, messages: list[AIMessage], system: str | None = None) -> str:
        return self._run("chat", lambda client: client.chat(messages, system))

    def _run(
        self,
        operation: str,
        call: Callable[[AIClient], StructuredModel | str],
    ) -> StructuredModel | str:
        try:
            result = self._run_primary_with_retry(operation, call)
            _log_ai_event(
                operation=operation,
                event="success",
                provider=_provider_name(self._primary),
                model=_model_name(self._primary),
                final=True,
            )
            return result
        except AIClientError as primary_error:
            if self._secondary is None or not _is_fallback_eligible(primary_error):
                _log_ai_event(
                    operation=operation,
                    event="failure",
                    provider=_provider_name(self._primary),
                    model=_model_name(self._primary),
                    category=_error_category(primary_error),
                    fallback_triggered=False,
                    final=True,
                )
                raise

            _log_ai_event(
                operation=operation,
                event="fallback_triggered",
                provider=_provider_name(self._primary),
                model=_model_name(self._primary),
                category=_error_category(primary_error),
                fallback_provider=_provider_name(self._secondary),
                fallback_model=_model_name(self._secondary),
            )
            try:
                result = call(self._secondary)
                _log_ai_event(
                    operation=operation,
                    event="success",
                    provider=_provider_name(self._secondary),
                    model=_model_name(self._secondary),
                    final=True,
                )
                return result
            except AIClientError as secondary_error:
                _log_ai_event(
                    operation=operation,
                    event="failure",
                    provider=_provider_name(self._secondary),
                    model=_model_name(self._secondary),
                    category=_error_category(secondary_error),
                    final=True,
                )
                raise AIProviderError(
                    "AI providers are unavailable for this request.",
                    category=_error_category(secondary_error),
                    provider=_provider_name(self._secondary),
                    model=_model_name(self._secondary),
                    retryable=False,
                ) from secondary_error

    def _run_primary_with_retry(
        self,
        operation: str,
        call: Callable[[AIClient], StructuredModel | str],
    ) -> StructuredModel | str:
        attempts = 0
        while True:
            try:
                _log_ai_event(
                    operation=operation,
                    event="attempt",
                    provider=_provider_name(self._primary),
                    model=_model_name(self._primary),
                    retry_attempt=attempts,
                )
                return call(self._primary)
            except AIClientError as exc:
                if not _is_retry_eligible(exc) or attempts >= self._retry_policy.max_retries:
                    raise
                attempts += 1
                _log_ai_event(
                    operation=operation,
                    event="retry",
                    provider=_provider_name(self._primary),
                    model=_model_name(self._primary),
                    category=_error_category(exc),
                    retry_attempt=attempts,
                )
                self._retry_policy.sleeper(self._retry_policy.backoff_seconds)


def _is_fallback_eligible(error: AIClientError) -> bool:
    return _error_category(error) in FALLBACK_ELIGIBLE_CATEGORIES


def _is_retry_eligible(error: AIClientError) -> bool:
    return _error_category(error) in RETRY_ELIGIBLE_CATEGORIES


def _error_category(error: AIClientError) -> AIErrorCategory:
    category = getattr(error, "category", None)
    if isinstance(category, AIErrorCategory):
        return category
    if isinstance(error, AITimeoutError):
        return AIErrorCategory.TIMEOUT
    if isinstance(error, InvalidStructuredOutputError):
        return AIErrorCategory.STRUCTURED_OUTPUT_ERROR
    return AIErrorCategory.UNKNOWN_PROVIDER_ERROR


def _provider_name(client: AIClient) -> str:
    value = getattr(client, "provider_name", None)
    return str(value) if value else client.__class__.__name__


def _model_name(client: AIClient) -> str | None:
    value = getattr(client, "model_name", None)
    return str(value) if value else None


def _log_ai_event(**fields: object) -> None:
    safe_fields = {key: value for key, value in fields.items() if value is not None}
    logger.info("ai_provider_event %s", safe_fields, extra={"ai": safe_fields})


def create_ai_client() -> AIClient:
    provider = settings.ai_provider.strip().lower()
    if provider == "gemini":
        from app.services.ai_providers.gemini import GeminiAIClient
        from app.services.ai_providers.openrouter import create_openrouter_client

        primary = GeminiAIClient(
            api_key=settings.gemini_api_key,
            model=settings.gemini_model,
            timeout_seconds=settings.ai_timeout_seconds,
        )
        if not settings.ai_fallback_enabled:
            return primary
        return FallbackAIClient(
            primary=primary,
            secondary=create_openrouter_client(settings),
            retry_policy=RetryPolicy(
                max_retries=settings.ai_retry_max_retries,
                backoff_seconds=settings.ai_retry_backoff_seconds,
            ),
        )

    raise AIProviderError(f"Unsupported AI provider: {settings.ai_provider}.")
