"""Loading and validation for masked task 1 and tuned task 2 output."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


class InputDataError(ValueError):
    """Raised when a task 1 or task 2 payload is invalid."""


MASKED_RESULT_FIELDS = (
    "schema_version",
    "conversation_id",
    "utterance_id",
    "masked_text",
    "has_masked_data",
    "masked_types",
)


TUNED_RESULT_FIELDS = (
    "schema_version",
    "conversation_id",
    "utterance_id",
    "tuned_text",
    "is_tuned",
    "has_unclear",
    "unclear_segments",
)


def load_masked_result(path: str | Path) -> dict[str, Any]:
    """Load and validate a task 1 masked result."""

    return validate_masked_result(_load_json(path, "masked result"))


def load_tuned_result(path: str | Path) -> dict[str, Any]:
    """Load and validate a task 2 result from an explicitly provided path.

    ``.json`` is the official filename convention, but the extension is not
    used to validate a caller-provided path.
    """

    return validate_tuned_result(_load_json(path, "tuned result"))


def _load_json(path: str | Path, description: str) -> object:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise InputDataError(f"{description} file contains malformed JSON") from error


def validate_masked_result(payload: object) -> dict[str, Any]:
    """Validate the task 1 masked-text API payload."""

    if not isinstance(payload, Mapping):
        raise InputDataError("masked result must be a JSON object")

    missing_fields = [field for field in MASKED_RESULT_FIELDS if field not in payload]
    if missing_fields:
        raise InputDataError(
            "masked result is missing required field(s): " + ", ".join(missing_fields)
        )

    if not isinstance(payload["schema_version"], str):
        raise InputDataError("schema_version must be a string")
    if not isinstance(payload["conversation_id"], str):
        raise InputDataError("conversation_id must be a string")
    utterance_id = payload["utterance_id"]
    if not isinstance(utterance_id, int) or isinstance(utterance_id, bool):
        raise InputDataError("utterance_id must be an integer")
    if not isinstance(payload["masked_text"], str):
        raise InputDataError("masked_text must be a string")
    if not isinstance(payload["has_masked_data"], bool):
        raise InputDataError("has_masked_data must be a boolean")
    if not isinstance(payload["masked_types"], list) or not all(
        isinstance(masked_type, str) for masked_type in payload["masked_types"]
    ):
        raise InputDataError("masked_types must be a list of strings")

    return dict(payload)


def validate_tuned_result(payload: object) -> dict[str, Any]:
    """Validate required task 2 fields without replacing any delivered value."""

    if not isinstance(payload, Mapping):
        raise InputDataError("tuned result must be a JSON object")

    missing_fields = [field for field in TUNED_RESULT_FIELDS if field not in payload]
    if missing_fields:
        raise InputDataError(
            "tuned result is missing required field(s): " + ", ".join(missing_fields)
        )

    if not isinstance(payload["schema_version"], str):
        raise InputDataError("schema_version must be a string")
    if not isinstance(payload["conversation_id"], str):
        raise InputDataError("conversation_id must be a string")
    utterance_id = payload["utterance_id"]
    if not isinstance(utterance_id, int) or isinstance(utterance_id, bool):
        raise InputDataError("utterance_id must be an integer")
    if not isinstance(payload["tuned_text"], str):
        raise InputDataError("tuned_text must be a string")
    if not isinstance(payload["is_tuned"], bool):
        raise InputDataError("is_tuned must be a boolean")
    if not isinstance(payload["has_unclear"], bool):
        raise InputDataError("has_unclear must be a boolean")
    if not isinstance(payload["unclear_segments"], list) or not all(
        isinstance(segment, str) for segment in payload["unclear_segments"]
    ):
        raise InputDataError("unclear_segments must be a list of strings")

    return dict(payload)
