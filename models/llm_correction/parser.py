"""Strict parser for the small JSON object returned by the LLM."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, NoReturn


_EXPECTED_FIELDS = frozenset({"tuned_text", "unclear_segments"})
MAX_LLM_RESPONSE_CHARS = 20_000
MAX_TUNED_TEXT_CHARS = 10_000
MAX_UNCLEAR_SEGMENTS = 100
MAX_UNCLEAR_SEGMENT_CHARS = 1_000


class LLMResponseError(ValueError):
    """Raised when an LLM response cannot be trusted as correction data."""


@dataclass(frozen=True)
class ParsedCorrection:
    """Validated fields that the LLM is permitted to decide."""

    tuned_text: str
    unclear_segments: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.tuned_text, str) or not self.tuned_text.strip():
            raise LLMResponseError("tuned_text must be a non-blank string")
        if len(self.tuned_text) > MAX_TUNED_TEXT_CHARS:
            raise LLMResponseError("tuned_text exceeds the allowed length")
        if not isinstance(self.unclear_segments, tuple):
            raise LLMResponseError("unclear_segments must be a tuple internally")
        if len(self.unclear_segments) > MAX_UNCLEAR_SEGMENTS:
            raise LLMResponseError("unclear_segments contains too many items")
        if not all(
            isinstance(segment, str) and segment.strip()
            for segment in self.unclear_segments
        ):
            raise LLMResponseError(
                "unclear_segments must contain only non-blank strings"
            )
        if any(
            len(segment) > MAX_UNCLEAR_SEGMENT_CHARS
            for segment in self.unclear_segments
        ):
            raise LLMResponseError("an unclear segment exceeds the allowed length")


def parse_correction_response(response_text: str) -> ParsedCorrection:
    """Accept only a standalone JSON object with the two allowed fields."""

    if not isinstance(response_text, str) or not response_text.strip():
        raise LLMResponseError("LLM response must be a non-blank string")
    if len(response_text) > MAX_LLM_RESPONSE_CHARS:
        raise LLMResponseError("LLM response exceeds the allowed length")

    parsing_failed = False
    try:
        payload = json.loads(
            response_text,
            object_pairs_hook=_object_without_duplicate_keys,
            parse_constant=_reject_non_standard_json_constant,
        )
    except (json.JSONDecodeError, RecursionError):
        parsing_failed = True

    if parsing_failed:
        raise LLMResponseError("LLM response must be one valid JSON object")

    if not isinstance(payload, dict):
        raise LLMResponseError("LLM response must be a JSON object")

    actual_fields = set(payload)
    missing_fields = _EXPECTED_FIELDS - actual_fields
    unexpected_fields = actual_fields - _EXPECTED_FIELDS
    if missing_fields:
        raise LLMResponseError("LLM response is missing required fields")
    if unexpected_fields:
        raise LLMResponseError("LLM response contains unexpected fields")

    tuned_text = payload["tuned_text"]
    unclear_segments = payload["unclear_segments"]
    if not isinstance(tuned_text, str) or not tuned_text.strip():
        raise LLMResponseError("tuned_text must be a non-blank string")
    if not isinstance(unclear_segments, list):
        raise LLMResponseError("unclear_segments must be a JSON array")
    if not all(
        isinstance(segment, str) and segment.strip()
        for segment in unclear_segments
    ):
        raise LLMResponseError(
            "unclear_segments must contain only non-blank strings"
        )

    return ParsedCorrection(
        tuned_text=tuned_text,
        unclear_segments=tuple(unclear_segments),
    )


def _object_without_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key, value in pairs:
        if key in payload:
            raise LLMResponseError("LLM response contains a duplicate field")
        payload[key] = value
    return payload


def _reject_non_standard_json_constant(_value: str) -> NoReturn:
    raise LLMResponseError("LLM response contains a non-standard JSON value")
