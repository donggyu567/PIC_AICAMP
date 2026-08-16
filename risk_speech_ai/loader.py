"""File loading and validation for task 1 STT and task 2 correction output."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


class InputDataError(ValueError):
    """Raised when an input file has an invalid task 1 or task 2 payload."""


TUNED_RESULT_FIELDS = (
    "utterance_id",
    "tuned_text",
    "is_tuned",
    "has_unclear",
    "unclear_segments",
)


def load_stt_text(path: str | Path) -> str:
    """Load raw STT text, removing only terminal CR/LF characters."""

    text = Path(path).read_text(encoding="utf-8")
    return text.rstrip("\r\n")


def load_tuned_result(path: str | Path) -> dict[str, Any]:
    """Load and validate a task 2 result from an explicitly provided path.

    ``.json`` is the official filename convention, but the extension is not
    used to validate a caller-provided path.
    """

    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise InputDataError("tuned result file contains malformed JSON") from error

    return validate_tuned_result(payload)


def validate_tuned_result(payload: object) -> dict[str, Any]:
    """Validate required task 2 fields without replacing any delivered value."""

    if not isinstance(payload, Mapping):
        raise InputDataError("tuned result must be a JSON object")

    missing_fields = [field for field in TUNED_RESULT_FIELDS if field not in payload]
    if missing_fields:
        raise InputDataError(
            "tuned result is missing required field(s): " + ", ".join(missing_fields)
        )

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
