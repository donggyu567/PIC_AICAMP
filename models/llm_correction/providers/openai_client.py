"""Privacy-conscious OpenAI Responses API adapter."""

from __future__ import annotations

import math
import os
from collections.abc import Mapping
from typing import Any

from ..client import LLMClientError


DEFAULT_OPENAI_MODEL = "gpt-5.6-luna"
DEFAULT_OPENAI_TIMEOUT_SECONDS = 10.0
DEFAULT_OPENAI_MAX_RETRIES = 2
DEFAULT_OPENAI_MAX_OUTPUT_TOKENS = 32_768


class OpenAIResponsesClient:
    """Return one strict JSON correction through the OpenAI Responses API."""

    def __init__(
        self,
        *,
        model: str | None = None,
        timeout_seconds: float | None = None,
        max_retries: int | None = None,
        max_output_tokens: int | None = None,
        sdk_client: Any | None = None,
    ) -> None:
        self._model = _resolve_model(model)
        self._timeout_seconds = _resolve_positive_float(
            timeout_seconds,
            environment_name="OPENAI_TIMEOUT_SECONDS",
            default=DEFAULT_OPENAI_TIMEOUT_SECONDS,
        )
        self._max_retries = _resolve_non_negative_integer(
            max_retries,
            environment_name="OPENAI_MAX_RETRIES",
            default=DEFAULT_OPENAI_MAX_RETRIES,
        )
        self._max_output_tokens = _resolve_positive_integer(
            max_output_tokens,
            environment_name="OPENAI_MAX_OUTPUT_TOKENS",
            default=DEFAULT_OPENAI_MAX_OUTPUT_TOKENS,
        )

        if sdk_client is None:
            sdk_client = _create_sdk_client(
                timeout_seconds=self._timeout_seconds,
                max_retries=self._max_retries,
            )

        responses_api = getattr(sdk_client, "responses", None)
        if not callable(getattr(responses_api, "create", None)):
            raise TypeError("sdk_client must provide responses.create")
        self._client = sdk_client

    def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        """Call OpenAI without state, identifiers, tools, or unmasked metadata."""

        _require_non_blank_prompt(system_prompt, "system_prompt")
        _require_non_blank_prompt(user_prompt, "user_prompt")

        request_failed = False
        response: Any | None = None
        try:
            response = self._client.responses.create(
                model=self._model,
                instructions=system_prompt,
                input=user_prompt,
                reasoning={"effort": "none"},
                store=False,
                max_output_tokens=self._max_output_tokens,
                text={"format": _correction_response_format()},
            )
        except Exception:
            request_failed = True

        if request_failed:
            raise LLMClientError("OpenAI provider request failed")

        response_read_failed = False
        status: object = None
        contains_refusal = False
        output_text: object = None
        try:
            status = getattr(response, "status", None)
            if status == "completed":
                contains_refusal = _response_contains_refusal(response)
                output_text = getattr(response, "output_text", None)
        except Exception:
            response_read_failed = True

        if response_read_failed:
            raise LLMClientError("OpenAI provider response could not be read")
        if status != "completed":
            raise LLMClientError("OpenAI provider did not complete the request")
        if contains_refusal:
            raise LLMClientError("OpenAI provider refused the correction request")

        if not isinstance(output_text, str) or not output_text.strip():
            raise LLMClientError("OpenAI provider returned no correction text")
        return output_text


def _create_sdk_client(*, timeout_seconds: float, max_retries: int) -> Any:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key or not api_key.strip():
        raise LLMClientError("OPENAI_API_KEY is not configured")

    openai_constructor: Any | None = None
    try:
        from openai import OpenAI
        openai_constructor = OpenAI
    except ImportError:
        pass

    if openai_constructor is None:
        raise LLMClientError("OpenAI SDK is not installed")

    initialization_failed = False
    sdk_client: Any | None = None
    try:
        sdk_client = openai_constructor(
            api_key=api_key.strip(),
            timeout=timeout_seconds,
            max_retries=max_retries,
        )
    except Exception:
        initialization_failed = True

    if initialization_failed or sdk_client is None:
        raise LLMClientError("OpenAI client initialization failed")
    return sdk_client


def _correction_response_format() -> dict[str, object]:
    return {
        "type": "json_schema",
        "name": "stt_correction",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "tuned_text": {"type": "string"},
                "unclear_segments": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
            "required": ["tuned_text", "unclear_segments"],
            "additionalProperties": False,
        },
    }


def _response_contains_refusal(response: object) -> bool:
    output_items = _read_member(response, "output")
    if not isinstance(output_items, (list, tuple)):
        return False

    for output_item in output_items:
        content_items = _read_member(output_item, "content")
        if not isinstance(content_items, (list, tuple)):
            continue
        for content_item in content_items:
            if _read_member(content_item, "type") == "refusal":
                return True
    return False


def _read_member(value: object, name: str) -> object:
    if isinstance(value, Mapping):
        return value.get(name)
    return getattr(value, name, None)


def _require_non_blank_prompt(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-blank string")
    return value


def _resolve_model(explicit_value: str | None) -> str:
    value = explicit_value
    if value is None:
        value = os.environ.get("OPENAI_MODEL", DEFAULT_OPENAI_MODEL)
    if not isinstance(value, str) or not value.strip():
        raise ValueError("OPENAI_MODEL must be a non-blank string")
    return value.strip()


def _resolve_positive_float(
    explicit_value: float | None,
    *,
    environment_name: str,
    default: float,
) -> float:
    value: object = explicit_value
    if value is None:
        value = os.environ.get(environment_name, default)
    if isinstance(value, bool):
        raise ValueError(f"{environment_name} must be a positive number")
    try:
        numeric_value = float(value)
    except (OverflowError, TypeError, ValueError):
        raise ValueError(
            f"{environment_name} must be a positive number"
        ) from None
    if not math.isfinite(numeric_value) or numeric_value <= 0:
        raise ValueError(f"{environment_name} must be a positive number")
    return numeric_value


def _resolve_non_negative_integer(
    explicit_value: int | None,
    *,
    environment_name: str,
    default: int,
) -> int:
    value: object = explicit_value
    if value is None:
        value = os.environ.get(environment_name, default)
    numeric_value = _strict_integer(value, environment_name)
    if numeric_value < 0:
        raise ValueError(f"{environment_name} must be zero or greater")
    return numeric_value


def _resolve_positive_integer(
    explicit_value: int | None,
    *,
    environment_name: str,
    default: int,
) -> int:
    value: object = explicit_value
    if value is None:
        value = os.environ.get(environment_name, default)
    numeric_value = _strict_integer(value, environment_name)
    if numeric_value <= 0:
        raise ValueError(f"{environment_name} must be a positive integer")
    return numeric_value


def _strict_integer(value: object, environment_name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{environment_name} must be an integer")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.isdecimal():
            return int(stripped)
    raise ValueError(f"{environment_name} must be an integer")
