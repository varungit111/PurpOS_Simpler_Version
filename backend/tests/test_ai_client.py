import json
import unittest
from io import BytesIO
from socket import timeout as SocketTimeout
from unittest.mock import patch
from urllib.error import HTTPError

from pydantic import BaseModel, Field

from app.services.ai_client import (
    AIErrorCategory,
    AIClient,
    AIClientError,
    AIMessage,
    FallbackAIClient,
    AIProviderError,
    AITimeoutError,
    InvalidStructuredOutputError,
    MalformedModelResponseError,
    MissingAIAPIKeyError,
    RetryPolicy,
)
from app.services.ai_providers.gemini import GeminiAIClient
from app.services.ai_providers.openrouter import OpenRouterAIClient


class StructuredReply(BaseModel):
    summary: str = Field(min_length=1)


class FakeAIClient:
    def generate_text(self, prompt: str, system: str | None = None) -> str:
        return f"{system}: {prompt}" if system else prompt

    def generate_structured(
        self,
        prompt: str,
        output_schema: type[StructuredReply],
        system: str | None = None,
    ) -> StructuredReply:
        return output_schema(summary=prompt)

    def chat(self, messages: list[AIMessage], system: str | None = None) -> str:
        return messages[-1].content


class FakeHTTPResponse:
    def __init__(self, payload: dict[str, object] | list[object] | bytes) -> None:
        if isinstance(payload, bytes):
            self._body = payload
        else:
            self._body = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "FakeHTTPResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None


def openrouter_payload(content: str | None) -> dict[str, object]:
    return {"choices": [{"message": {"content": content}}]}


class SequencedAIClient:
    provider_name = "sequenced"
    model_name = "test-model"

    def __init__(self, *results: object) -> None:
        self.results = list(results)
        self.calls = 0

    def generate_text(self, prompt: str, system: str | None = None) -> str:
        return self._next()

    def generate_structured(
        self,
        prompt: str,
        output_schema: type[StructuredReply],
        system: str | None = None,
    ) -> StructuredReply:
        result = self._next()
        if isinstance(result, StructuredReply):
            return result
        return output_schema(summary=str(result))

    def chat(self, messages: list[AIMessage], system: str | None = None) -> str:
        return self._next()

    def _next(self):
        self.calls += 1
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def provider_error(category: AIErrorCategory, status_code: int | None = None) -> AIProviderError:
    return AIProviderError(
        f"{category.value} failed",
        category=category,
        provider="gemini",
        model="gemini-test",
        status_code=status_code,
        retryable=category
        in {
            AIErrorCategory.RATE_LIMIT,
            AIErrorCategory.QUOTA_EXHAUSTED,
            AIErrorCategory.UNAVAILABLE,
            AIErrorCategory.NETWORK_ERROR,
            AIErrorCategory.PROVIDER_5XX,
        },
    )


class AIClientTests(unittest.TestCase):
    def test_fake_client_satisfies_ai_client_contract(self) -> None:
        client: AIClient = FakeAIClient()

        self.assertEqual(client.generate_text("hello"), "hello")
        self.assertEqual(
            client.generate_structured("hello", StructuredReply).summary,
            "hello",
        )
        self.assertEqual(
            client.chat([AIMessage(role="user", content="last")]),
            "last",
        )

    def test_gemini_requires_api_key(self) -> None:
        with self.assertRaises(MissingAIAPIKeyError):
            GeminiAIClient(api_key=None, model="gemini-test", timeout_seconds=1)

    def test_gemini_generate_text_extracts_candidate_text(self) -> None:
        payload = {
            "candidates": [
                {"content": {"parts": [{"text": "Generated response"}]}}
            ]
        }

        with patch(
            "app.services.ai_providers.gemini.urlopen",
            return_value=FakeHTTPResponse(payload),
        ):
            client = GeminiAIClient(
                api_key="test-key", model="gemini-test", timeout_seconds=1
            )

            self.assertEqual(client.generate_text("Prompt"), "Generated response")

    def test_gemini_generate_structured_validates_schema(self) -> None:
        payload = {
            "candidates": [
                {"content": {"parts": [{"text": '{"summary": "Usable"}'}]}}
            ]
        }

        with patch(
            "app.services.ai_providers.gemini.urlopen",
            return_value=FakeHTTPResponse(payload),
        ) as mocked_urlopen:
            client = GeminiAIClient(
                api_key="test-key", model="gemini-test", timeout_seconds=1
            )

            result = client.generate_structured("Prompt", StructuredReply)

        self.assertEqual(result.summary, "Usable")
        request_payload = json.loads(mocked_urlopen.call_args.args[0].data)
        generation_config = request_payload["generationConfig"]
        self.assertIn("responseJsonSchema", generation_config)
        self.assertNotIn("responseSchema", generation_config)

    def test_gemini_rejects_invalid_structured_output(self) -> None:
        payload = {
            "candidates": [
                {"content": {"parts": [{"text": '{"summary": ""}'}]}}
            ]
        }

        with patch(
            "app.services.ai_providers.gemini.urlopen",
            return_value=FakeHTTPResponse(payload),
        ):
            client = GeminiAIClient(
                api_key="test-key", model="gemini-test", timeout_seconds=1
            )

            with self.assertRaises(InvalidStructuredOutputError):
                client.generate_structured("Prompt", StructuredReply)

    def test_gemini_rejects_malformed_response_shape(self) -> None:
        with patch(
            "app.services.ai_providers.gemini.urlopen",
            return_value=FakeHTTPResponse({"candidates": []}),
        ):
            client = GeminiAIClient(
                api_key="test-key", model="gemini-test", timeout_seconds=1
            )

            with self.assertRaises(MalformedModelResponseError):
                client.generate_text("Prompt")

    def test_gemini_rejects_non_json_response(self) -> None:
        with patch(
            "app.services.ai_providers.gemini.urlopen",
            return_value=FakeHTTPResponse(b"not-json"),
        ):
            client = GeminiAIClient(
                api_key="test-key", model="gemini-test", timeout_seconds=1
            )

            with self.assertRaises(MalformedModelResponseError):
                client.generate_text("Prompt")

    def test_gemini_wraps_provider_errors(self) -> None:
        error = HTTPError(
            url="https://example.test",
            code=429,
            msg="rate limited",
            hdrs=None,
            fp=BytesIO(b'{"error":"rate limited"}'),
        )

        with patch("app.services.ai_providers.gemini.urlopen", side_effect=error):
            client = GeminiAIClient(
                api_key="test-key", model="gemini-test", timeout_seconds=1
            )

            with self.assertRaises(AIProviderError) as raised:
                client.generate_text("Prompt")

        self.assertEqual(raised.exception.category, AIErrorCategory.RATE_LIMIT)

    def test_gemini_wraps_timeouts(self) -> None:
        with patch(
            "app.services.ai_providers.gemini.urlopen",
            side_effect=SocketTimeout("timed out"),
        ):
            client = GeminiAIClient(
                api_key="test-key", model="gemini-test", timeout_seconds=1
            )

            with self.assertRaises(AITimeoutError):
                client.generate_text("Prompt")

    def test_gemini_classifies_quota_exhaustion(self) -> None:
        error = HTTPError(
            url="https://example.test",
            code=429,
            msg="quota exhausted",
            hdrs=None,
            fp=BytesIO(b'{"error":{"status":"RESOURCE_EXHAUSTED","message":"quota exhausted"}}'),
        )

        with patch("app.services.ai_providers.gemini.urlopen", side_effect=error):
            client = GeminiAIClient(
                api_key="test-key", model="gemini-test", timeout_seconds=1
            )

            with self.assertRaises(AIProviderError) as raised:
                client.generate_text("Prompt")

        self.assertEqual(raised.exception.category, AIErrorCategory.QUOTA_EXHAUSTED)

    def test_fallback_not_called_when_gemini_succeeds(self) -> None:
        primary = SequencedAIClient("primary")
        secondary = SequencedAIClient("secondary")
        client = FallbackAIClient(primary=primary, secondary=secondary)

        self.assertEqual(client.generate_text("Prompt"), "primary")
        self.assertEqual(primary.calls, 1)
        self.assertEqual(secondary.calls, 0)

    def test_fallback_called_for_rate_limit_and_quota(self) -> None:
        for category in (AIErrorCategory.RATE_LIMIT, AIErrorCategory.QUOTA_EXHAUSTED):
            with self.subTest(category=category):
                primary = SequencedAIClient(provider_error(category))
                secondary = SequencedAIClient("secondary")
                client = FallbackAIClient(primary=primary, secondary=secondary)

                self.assertEqual(client.generate_text("Prompt"), "secondary")
                self.assertEqual(secondary.calls, 1)

    def test_fallback_retries_503_before_openrouter(self) -> None:
        sleeps: list[float] = []
        primary = SequencedAIClient(
            provider_error(AIErrorCategory.UNAVAILABLE, 503),
            provider_error(AIErrorCategory.UNAVAILABLE, 503),
        )
        secondary = SequencedAIClient("secondary")
        client = FallbackAIClient(
            primary=primary,
            secondary=secondary,
            retry_policy=RetryPolicy(
                max_retries=1,
                backoff_seconds=0.01,
                sleeper=sleeps.append,
            ),
        )

        self.assertEqual(client.generate_text("Prompt"), "secondary")
        self.assertEqual(primary.calls, 2)
        self.assertEqual(secondary.calls, 1)
        self.assertEqual(sleeps, [0.01])

    def test_fallback_called_for_timeout_network_and_5xx(self) -> None:
        errors: list[AIClientError] = [
            AITimeoutError("timed out", provider="gemini", model="gemini-test"),
            provider_error(AIErrorCategory.NETWORK_ERROR),
            provider_error(AIErrorCategory.PROVIDER_5XX, 500),
        ]
        for error in errors:
            with self.subTest(error=error):
                primary = SequencedAIClient(error)
                secondary = SequencedAIClient("secondary")
                client = FallbackAIClient(
                    primary=primary,
                    secondary=secondary,
                    retry_policy=RetryPolicy(max_retries=0, sleeper=lambda _: None),
                )
                self.assertEqual(client.generate_text("Prompt"), "secondary")

    def test_fallback_rejects_invalid_request_and_auth_errors(self) -> None:
        for category in (AIErrorCategory.INVALID_REQUEST, AIErrorCategory.AUTHENTICATION):
            with self.subTest(category=category):
                primary = SequencedAIClient(provider_error(category, 400))
                secondary = SequencedAIClient("secondary")
                client = FallbackAIClient(primary=primary, secondary=secondary)

                with self.assertRaises(AIProviderError):
                    client.generate_text("Prompt")
                self.assertEqual(secondary.calls, 0)

    def test_both_providers_fail_returns_safe_ai_error(self) -> None:
        primary = SequencedAIClient(provider_error(AIErrorCategory.RATE_LIMIT, 429))
        secondary = SequencedAIClient(provider_error(AIErrorCategory.UNAVAILABLE, 503))
        client = FallbackAIClient(primary=primary, secondary=secondary)

        with self.assertRaises(AIProviderError) as raised:
            client.generate_text("Prompt")

        self.assertIn("AI providers are unavailable", str(raised.exception))

    def test_fallback_disabled_keeps_gemini_failure(self) -> None:
        primary = SequencedAIClient(provider_error(AIErrorCategory.RATE_LIMIT, 429))
        client = FallbackAIClient(primary=primary, secondary=None)

        with self.assertRaises(AIProviderError) as raised:
            client.generate_text("Prompt")

        self.assertEqual(str(raised.exception), "rate_limit failed")

    def test_openrouter_generate_structured_validates_schema(self) -> None:
        payload = openrouter_payload('{"summary": "Usable"}')

        with patch(
            "app.services.ai_providers.openrouter.urlopen",
            return_value=FakeHTTPResponse(payload),
        ) as mocked_urlopen:
            client = OpenRouterAIClient(
                api_key="test-key",
                models=["free/model"],
                timeout_seconds=1,
                free_only=True,
                free_model_allowlist={"free/model"},
            )

            result = client.generate_structured("Prompt", StructuredReply)

        self.assertEqual(result.summary, "Usable")
        request_payload = json.loads(mocked_urlopen.call_args.args[0].data)
        self.assertEqual(
            request_payload["response_format"],
            {
                "type": "json_schema",
                "json_schema": {
                    "name": "StructuredReply",
                    "strict": True,
                    "schema": StructuredReply.model_json_schema(),
                },
            },
        )
        self.assertEqual(request_payload["provider"], {"require_parameters": True})
        self.assertEqual(request_payload["model"], "free/model")

    def test_openrouter_malformed_structured_response_is_rejected(self) -> None:
        payload = openrouter_payload('{"summary": ""}')

        with patch(
            "app.services.ai_providers.openrouter.urlopen",
            return_value=FakeHTTPResponse(payload),
        ):
            client = OpenRouterAIClient(
                api_key="test-key",
                models=["free/model"],
                timeout_seconds=1,
                free_only=True,
                free_model_allowlist={"free/model"},
            )

            with self.assertRaises(InvalidStructuredOutputError):
                client.generate_structured("Prompt", StructuredReply)

    def test_openrouter_empty_structured_response_advances_model(self) -> None:
        with patch(
            "app.services.ai_providers.openrouter.urlopen",
            side_effect=[
                FakeHTTPResponse(openrouter_payload("")),
                FakeHTTPResponse(openrouter_payload('{"summary": "Fallback"}')),
            ],
        ) as mocked_urlopen:
            client = OpenRouterAIClient(
                api_key="test-key",
                models=["free/first", "free/second"],
                timeout_seconds=1,
                free_only=True,
                free_model_allowlist={"free/first", "free/second"},
            )

            result = client.generate_structured("Prompt", StructuredReply)

        self.assertEqual(result.summary, "Fallback")
        attempted = [
            json.loads(call.args[0].data)["model"]
            for call in mocked_urlopen.call_args_list
        ]
        self.assertEqual(attempted, ["free/first", "free/second"])

    def test_openrouter_malformed_json_advances_model(self) -> None:
        with patch(
            "app.services.ai_providers.openrouter.urlopen",
            side_effect=[
                FakeHTTPResponse(openrouter_payload("not-json")),
                FakeHTTPResponse(openrouter_payload('{"summary": "Fallback"}')),
            ],
        ) as mocked_urlopen:
            client = OpenRouterAIClient(
                api_key="test-key",
                models=["free/first", "free/second"],
                timeout_seconds=1,
                free_only=True,
                free_model_allowlist={"free/first", "free/second"},
            )

            result = client.generate_structured("Prompt", StructuredReply)

        self.assertEqual(result.summary, "Fallback")
        self.assertEqual(mocked_urlopen.call_count, 2)

    def test_openrouter_validation_failure_advances_model(self) -> None:
        with patch(
            "app.services.ai_providers.openrouter.urlopen",
            side_effect=[
                FakeHTTPResponse(openrouter_payload('{"summary": ""}')),
                FakeHTTPResponse(openrouter_payload('{"summary": "Fallback"}')),
            ],
        ) as mocked_urlopen:
            client = OpenRouterAIClient(
                api_key="test-key",
                models=["free/first", "free/second"],
                timeout_seconds=1,
                free_only=True,
                free_model_allowlist={"free/first", "free/second"},
            )

            result = client.generate_structured("Prompt", StructuredReply)

        self.assertEqual(result.summary, "Fallback")
        self.assertEqual(mocked_urlopen.call_count, 2)

    def test_openrouter_all_unusable_structured_outputs_raise_final_error(
        self,
    ) -> None:
        with patch(
            "app.services.ai_providers.openrouter.urlopen",
            side_effect=[
                FakeHTTPResponse(openrouter_payload("not-json")),
                FakeHTTPResponse(openrouter_payload('{"summary": ""}')),
            ],
        ):
            client = OpenRouterAIClient(
                api_key="test-key",
                models=["free/first", "free/second"],
                timeout_seconds=1,
                free_only=True,
                free_model_allowlist={"free/first", "free/second"},
            )

            with self.assertRaises(InvalidStructuredOutputError):
                client.generate_structured("Prompt", StructuredReply)

    def test_openrouter_structured_http_429_advances_model(self) -> None:
        rate_limit = HTTPError(
            url="https://example.test",
            code=429,
            msg="rate limited",
            hdrs=None,
            fp=BytesIO(b'{"error":"rate limited"}'),
        )

        with patch(
            "app.services.ai_providers.openrouter.urlopen",
            side_effect=[
                rate_limit,
                FakeHTTPResponse(openrouter_payload('{"summary": "Fallback"}')),
            ],
        ) as mocked_urlopen:
            client = OpenRouterAIClient(
                api_key="test-key",
                models=["free/first", "free/second"],
                timeout_seconds=1,
                free_only=True,
                free_model_allowlist={"free/first", "free/second"},
            )

            result = client.generate_structured("Prompt", StructuredReply)

        self.assertEqual(result.summary, "Fallback")
        self.assertEqual(mocked_urlopen.call_count, 2)

    def test_openrouter_auth_and_invalid_request_errors_do_not_advance(self) -> None:
        for status_code, category in (
            (401, AIErrorCategory.AUTHENTICATION),
            (400, AIErrorCategory.INVALID_REQUEST),
        ):
            with self.subTest(status_code=status_code):
                provider_error_response = HTTPError(
                    url="https://example.test",
                    code=status_code,
                    msg="provider error",
                    hdrs=None,
                    fp=BytesIO(b'{"error":"provider error"}'),
                )
                with patch(
                    "app.services.ai_providers.openrouter.urlopen",
                    side_effect=provider_error_response,
                ) as mocked_urlopen:
                    client = OpenRouterAIClient(
                        api_key="test-key",
                        models=["free/first", "free/second"],
                        timeout_seconds=1,
                        free_only=True,
                        free_model_allowlist={"free/first", "free/second"},
                    )

                    with self.assertRaises(AIProviderError) as raised:
                        client.generate_structured("Prompt", StructuredReply)

                self.assertEqual(raised.exception.category, category)
                self.assertEqual(mocked_urlopen.call_count, 1)

    def test_openrouter_free_only_rejects_non_allowlisted_models(self) -> None:
        with self.assertRaises(AIProviderError) as raised:
            OpenRouterAIClient(
                api_key="test-key",
                models=["paid/model"],
                timeout_seconds=1,
                free_only=True,
                free_model_allowlist={"free/model"},
            )

        self.assertEqual(raised.exception.category, AIErrorCategory.CONFIGURATION)

    def test_openrouter_free_only_does_not_choose_arbitrary_models(self) -> None:
        with self.assertRaises(AIProviderError):
            OpenRouterAIClient(
                api_key="test-key",
                models=["free/model"],
                timeout_seconds=1,
                free_only=True,
                free_model_allowlist=set(),
            )

    def test_openrouter_free_model_is_accepted_only_when_allowlisted(self) -> None:
        OpenRouterAIClient(
            api_key="test-key",
            models=["openrouter/free"],
            timeout_seconds=1,
            free_only=True,
            free_model_allowlist={"openrouter/free"},
        )

        with self.assertRaises(AIProviderError):
            OpenRouterAIClient(
                api_key="test-key",
                models=["openrouter/free"],
                timeout_seconds=1,
                free_only=True,
                free_model_allowlist={"free/model"},
            )

    def test_provider_logging_contains_no_api_keys(self) -> None:
        primary = SequencedAIClient(provider_error(AIErrorCategory.RATE_LIMIT, 429))
        secondary = SequencedAIClient("secondary")
        client = FallbackAIClient(primary=primary, secondary=secondary)

        with self.assertLogs("app.services.ai_client", level="INFO") as logs:
            client.generate_text("Prompt")

        combined = "\n".join(logs.output)
        self.assertIn("fallback_triggered", combined)
        self.assertNotIn("test-key", combined)


if __name__ == "__main__":
    unittest.main()
