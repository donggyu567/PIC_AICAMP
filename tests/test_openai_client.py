"""Unit tests for the OpenAI Responses API adapter."""

from __future__ import annotations

import os
import sys
import unittest
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

from models.llm_correction import LLMClientError, OpenAIResponsesClient


VALID_MODEL_RESPONSE = (
    '{"tuned_text":"[PERSON] 씨, 안녕하세요.","unclear_segments":[]}'
)


class StubResponsesAPI:
    def __init__(
        self,
        *,
        output_text: str = VALID_MODEL_RESPONSE,
        status: str = "completed",
        error: Exception | None = None,
        refusal: str | None = None,
    ) -> None:
        self.output_text = output_text
        self.status = status
        self.error = error
        self.refusal = refusal
        self.calls: list[dict[str, object]] = []

    def create(self, **parameters: object) -> SimpleNamespace:
        self.calls.append(parameters)
        if self.error is not None:
            raise self.error
        output = []
        if self.refusal is not None:
            output = [
                SimpleNamespace(
                    content=[
                        SimpleNamespace(type="refusal", refusal=self.refusal)
                    ]
                )
            ]
        return SimpleNamespace(
            status=self.status,
            output_text=self.output_text,
            output=output,
        )


class StubOpenAIClient:
    def __init__(self, responses: object) -> None:
        self.responses = responses


class ResponseWithBrokenOutput:
    status = "completed"

    @property
    def output(self) -> object:
        raise RuntimeError("sensitive malformed response")


def client_with(responses: StubResponsesAPI) -> OpenAIResponsesClient:
    return OpenAIResponsesClient(
        model="gpt-5.6-luna",
        timeout_seconds=10,
        max_retries=2,
        max_output_tokens=1024,
        sdk_client=StubOpenAIClient(responses),
    )


class OpenAIResponsesClientTests(unittest.TestCase):
    def test_uses_stateless_structured_output_without_identifiers(self) -> None:
        responses = StubResponsesAPI()
        client = client_with(responses)

        user_prompt = (
            '다음 JSON 데이터의 masked_text만 보정하라.\n'
            '{"masked_text":"[PERSON] 씨 안녕하세요"}'
        )
        result = client.complete(
            system_prompt="시스템 규칙",
            user_prompt=user_prompt,
        )

        self.assertEqual(VALID_MODEL_RESPONSE, result)
        self.assertEqual(1, len(responses.calls))
        request = responses.calls[0]
        self.assertEqual(
            {
                "model",
                "instructions",
                "input",
                "reasoning",
                "store",
                "max_output_tokens",
                "text",
            },
            set(request),
        )
        self.assertEqual("gpt-5.6-luna", request["model"])
        self.assertEqual("시스템 규칙", request["instructions"])
        self.assertEqual(user_prompt, request["input"])
        self.assertFalse(request["store"])
        self.assertEqual({"effort": "none"}, request["reasoning"])
        self.assertEqual(1024, request["max_output_tokens"])

        response_format = request["text"]["format"]
        self.assertEqual("json_schema", response_format["type"])
        self.assertTrue(response_format["strict"])
        schema = response_format["schema"]
        self.assertEqual(
            {"tuned_text", "unclear_segments"},
            set(schema["properties"]),
        )
        self.assertEqual(
            ["tuned_text", "unclear_segments"],
            schema["required"],
        )
        self.assertFalse(schema["additionalProperties"])

    def test_builds_the_sdk_from_environment_settings(self) -> None:
        responses = StubResponsesAPI()
        constructor_arguments: dict[str, object] = {}

        def fake_openai_constructor(**arguments: object) -> StubOpenAIClient:
            constructor_arguments.update(arguments)
            return StubOpenAIClient(responses)

        fake_openai_module = ModuleType("openai")
        fake_openai_module.OpenAI = fake_openai_constructor
        environment = {
            "OPENAI_API_KEY": "not-a-real-api-key",
            "OPENAI_MODEL": "gpt-5.6-luna",
            "OPENAI_TIMEOUT_SECONDS": "12.5",
            "OPENAI_MAX_RETRIES": "1",
            "OPENAI_MAX_OUTPUT_TOKENS": "512",
        }

        with patch.dict(os.environ, environment, clear=True), patch.dict(
            sys.modules,
            {"openai": fake_openai_module},
        ):
            client = OpenAIResponsesClient()
            client.complete(
                system_prompt="시스템 규칙",
                user_prompt='{"masked_text":"마스킹된 문장"}',
            )

        self.assertEqual(
            {
                "api_key": "not-a-real-api-key",
                "timeout": 12.5,
                "max_retries": 1,
            },
            constructor_arguments,
        )
        request = responses.calls[0]
        self.assertEqual("gpt-5.6-luna", request["model"])
        self.assertEqual(512, request["max_output_tokens"])

    def test_requires_an_api_key_before_creating_the_real_sdk(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(
                LLMClientError,
                "OPENAI_API_KEY is not configured",
            ):
                OpenAIResponsesClient()

    def test_sanitizes_provider_errors(self) -> None:
        secret_message = "raw transcript and provider-secret-value"
        responses = StubResponsesAPI(error=RuntimeError(secret_message))
        client = client_with(responses)

        with self.assertRaises(LLMClientError) as raised:
            client.complete(
                system_prompt="시스템 규칙",
                user_prompt='{"masked_text":"[PERSON]의 문장"}',
            )

        self.assertEqual("OpenAI provider request failed", str(raised.exception))
        self.assertNotIn(secret_message, str(raised.exception))
        self.assertIsNone(raised.exception.__cause__)
        self.assertIsNone(raised.exception.__context__)

    def test_rejects_an_incomplete_response(self) -> None:
        responses = StubResponsesAPI(status="incomplete")
        client = client_with(responses)

        with self.assertRaisesRegex(LLMClientError, "did not complete"):
            client.complete(
                system_prompt="시스템 규칙",
                user_prompt='{"masked_text":"마스킹된 문장"}',
            )

    def test_rejects_a_blank_response(self) -> None:
        responses = StubResponsesAPI(output_text="   ")
        client = client_with(responses)

        with self.assertRaisesRegex(LLMClientError, "no correction text"):
            client.complete(
                system_prompt="시스템 규칙",
                user_prompt='{"masked_text":"마스킹된 문장"}',
            )

    def test_rejects_a_refusal_without_exposing_its_text(self) -> None:
        refusal_text = "sensitive refusal details"
        responses = StubResponsesAPI(refusal=refusal_text)
        client = client_with(responses)

        with self.assertRaises(LLMClientError) as raised:
            client.complete(
                system_prompt="시스템 규칙",
                user_prompt='{"masked_text":"마스킹된 문장"}',
            )

        self.assertEqual(
            "OpenAI provider refused the correction request",
            str(raised.exception),
        )
        self.assertNotIn(refusal_text, str(raised.exception))

    def test_sanitizes_errors_raised_while_reading_the_response(self) -> None:
        sensitive_message = "sensitive malformed response"

        class BrokenResponsesAPI:
            def create(self, **_parameters: object) -> ResponseWithBrokenOutput:
                return ResponseWithBrokenOutput()

        client = OpenAIResponsesClient(
            model="gpt-5.6-luna",
            timeout_seconds=10,
            max_retries=2,
            max_output_tokens=1024,
            sdk_client=StubOpenAIClient(BrokenResponsesAPI()),
        )

        with self.assertRaises(LLMClientError) as raised:
            client.complete(
                system_prompt="시스템 규칙",
                user_prompt='{"masked_text":"마스킹된 문장"}',
            )

        self.assertEqual(
            "OpenAI provider response could not be read",
            str(raised.exception),
        )
        self.assertNotIn(sensitive_message, str(raised.exception))
        self.assertIsNone(raised.exception.__cause__)
        self.assertIsNone(raised.exception.__context__)

    def test_rejects_invalid_configuration_before_using_the_sdk(self) -> None:
        responses = StubResponsesAPI()
        sdk_client = StubOpenAIClient(responses)

        with self.assertRaisesRegex(ValueError, "OPENAI_MODEL"):
            OpenAIResponsesClient(model=" ", sdk_client=sdk_client)
        with self.assertRaisesRegex(ValueError, "positive integer"):
            OpenAIResponsesClient(
                max_output_tokens=0,
                sdk_client=sdk_client,
            )

        self.assertEqual([], responses.calls)

    def test_rejects_a_blank_prompt_before_calling_the_provider(self) -> None:
        responses = StubResponsesAPI()
        client = client_with(responses)

        with self.assertRaisesRegex(ValueError, "system_prompt"):
            client.complete(system_prompt="", user_prompt="마스킹된 문장")

        self.assertEqual([], responses.calls)


if __name__ == "__main__":
    unittest.main()
