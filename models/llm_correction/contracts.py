"""Strict, versioned contracts for masked STT correction data."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass


SUPPORTED_SCHEMA_VERSION = "1.0"
UNCLEAR_TOKEN = "[불명확]"

ALLOWED_MASKED_TYPES = frozenset(
    {
        "PERSON",
        "PHONE_NUMBER",
        "ACCOUNT_NUMBER",
        "RRN",
        "OTP",
        "ADDRESS",
    }
)

_BRACKETED_TOKEN_PATTERN = re.compile(r"\[[^\[\]\r\n]+\]")
_ALLOWED_MASK_TOKENS = frozenset(
    f"[{masked_type}]" for masked_type in ALLOWED_MASKED_TYPES
)
_MASKED_TRANSCRIPT_FIELDS = frozenset(
    {
        "schema_version",
        "conversation_id",
        "utterance_id",
        "masked_text",
        "has_masked_data",
        "masked_types",
    }
)
_CORRECTION_RESULT_FIELDS = frozenset(
    {
        "schema_version",
        "conversation_id",
        "utterance_id",
        "tuned_text",
        "is_tuned",
        "has_unclear",
        "unclear_segments",
    }
)


class ContractError(ValueError):
    """Raised when data violates an inter-stage contract."""


@dataclass(frozen=True)
class MaskedTranscript:
    """One tablet-masked utterance accepted by the correction stage."""

    schema_version: str
    conversation_id: str
    utterance_id: int
    masked_text: str
    has_masked_data: bool
    masked_types: tuple[str, ...]

    def __post_init__(self) -> None:
        """Protect invariants even when the constructor is called directly."""

        _validate_schema_version(self.schema_version)
        _validate_conversation_id(self.conversation_id)
        _require_positive_integer(self.utterance_id, "utterance_id")
        _require_non_blank_string(self.masked_text, "masked_text")
        _require_boolean(self.has_masked_data, "has_masked_data")
        _require_string_tuple(self.masked_types, "masked_types")
        _validate_masked_types(self.masked_types, reject_duplicates=True)

        text_masked_types = _extract_masked_types(self.masked_text)
        if set(self.masked_types) != set(text_masked_types):
            raise ContractError(
                "masked_types must exactly match the masking tokens in masked_text"
            )
        if self.has_masked_data != bool(text_masked_types):
            raise ContractError(
                "has_masked_data must be true exactly when masked_text contains "
                "masking tokens"
            )

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> MaskedTranscript:
        """Validate an API-shaped mapping and create an immutable value."""

        _validate_payload_shape(
            payload,
            expected_fields=_MASKED_TRANSCRIPT_FIELDS,
            description="masked transcript",
        )

        schema_version = _validate_schema_version(payload["schema_version"])
        conversation_id = _validate_conversation_id(payload["conversation_id"])
        utterance_id = _require_positive_integer(
            payload["utterance_id"], "utterance_id"
        )
        masked_text = _require_non_blank_string(
            payload["masked_text"], "masked_text"
        )
        has_masked_data = _require_boolean(
            payload["has_masked_data"], "has_masked_data"
        )
        masked_types = _require_string_array(
            payload["masked_types"], "masked_types"
        )

        return cls(
            schema_version=schema_version,
            conversation_id=conversation_id,
            utterance_id=utterance_id,
            masked_text=masked_text,
            has_masked_data=has_masked_data,
            masked_types=masked_types,
        )

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation."""

        return {
            "schema_version": self.schema_version,
            "conversation_id": self.conversation_id,
            "utterance_id": self.utterance_id,
            "masked_text": self.masked_text,
            "has_masked_data": self.has_masked_data,
            "masked_types": list(self.masked_types),
        }


@dataclass(frozen=True)
class CorrectionResult:
    """Validated output of the LLM correction stage."""

    schema_version: str
    conversation_id: str
    utterance_id: int
    tuned_text: str
    is_tuned: bool
    has_unclear: bool
    unclear_segments: tuple[str, ...]

    def __post_init__(self) -> None:
        """Protect invariants even when the constructor is called directly."""

        _validate_schema_version(self.schema_version)
        _validate_conversation_id(self.conversation_id)
        _require_positive_integer(self.utterance_id, "utterance_id")
        _require_non_blank_string(self.tuned_text, "tuned_text")
        _require_boolean(self.is_tuned, "is_tuned")
        _require_boolean(self.has_unclear, "has_unclear")
        _require_string_tuple(self.unclear_segments, "unclear_segments")
        _extract_masked_types(self.tuned_text, allow_unclear=True)

        unclear_count = self.tuned_text.count(UNCLEAR_TOKEN)
        if self.has_unclear != bool(self.unclear_segments):
            raise ContractError(
                "has_unclear must be true exactly when unclear_segments is non-empty"
            )
        if unclear_count != len(self.unclear_segments):
            raise ContractError(
                "each unclear_segments item must correspond to one [불명확] token"
            )

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> CorrectionResult:
        """Validate a correction-result mapping and create an immutable value."""

        _validate_payload_shape(
            payload,
            expected_fields=_CORRECTION_RESULT_FIELDS,
            description="correction result",
        )

        schema_version = _validate_schema_version(payload["schema_version"])
        conversation_id = _validate_conversation_id(payload["conversation_id"])
        utterance_id = _require_positive_integer(
            payload["utterance_id"], "utterance_id"
        )
        tuned_text = _require_non_blank_string(payload["tuned_text"], "tuned_text")
        is_tuned = _require_boolean(payload["is_tuned"], "is_tuned")
        has_unclear = _require_boolean(payload["has_unclear"], "has_unclear")
        unclear_segments = _require_string_array(
            payload["unclear_segments"], "unclear_segments"
        )

        return cls(
            schema_version=schema_version,
            conversation_id=conversation_id,
            utterance_id=utterance_id,
            tuned_text=tuned_text,
            is_tuned=is_tuned,
            has_unclear=has_unclear,
            unclear_segments=unclear_segments,
        )

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation."""

        return {
            "schema_version": self.schema_version,
            "conversation_id": self.conversation_id,
            "utterance_id": self.utterance_id,
            "tuned_text": self.tuned_text,
            "is_tuned": self.is_tuned,
            "has_unclear": self.has_unclear,
            "unclear_segments": list(self.unclear_segments),
        }


def validate_masking_token_preservation(
    masked_text: str,
    tuned_text: str,
) -> None:
    """Reject a correction that adds, removes, or changes masking tokens."""

    source_text = _require_non_blank_string(masked_text, "masked_text")
    corrected_text = _require_non_blank_string(tuned_text, "tuned_text")
    source_tokens = _extract_masked_types(source_text)
    corrected_tokens = _extract_masked_types(corrected_text, allow_unclear=True)

    if source_tokens != corrected_tokens:
        raise ContractError(
            "tuned_text must preserve every masking token in its original order"
        )


def validate_correction_against_input(
    transcript: MaskedTranscript,
    result: CorrectionResult,
) -> None:
    """Validate correlation and derived values across the two contracts."""

    if not isinstance(transcript, MaskedTranscript):
        raise TypeError("transcript must be a MaskedTranscript")
    if not isinstance(result, CorrectionResult):
        raise TypeError("result must be a CorrectionResult")

    if transcript.schema_version != result.schema_version:
        raise ContractError("correction result schema_version does not match input")
    if transcript.conversation_id != result.conversation_id:
        raise ContractError("correction result conversation_id does not match input")
    if transcript.utterance_id != result.utterance_id:
        raise ContractError("correction result utterance_id does not match input")

    validate_masking_token_preservation(
        transcript.masked_text,
        result.tuned_text,
    )

    expected_is_tuned = transcript.masked_text != result.tuned_text
    if result.is_tuned != expected_is_tuned:
        raise ContractError(
            "is_tuned must indicate whether tuned_text differs from masked_text"
        )

    search_start = 0
    for segment in result.unclear_segments:
        segment_index = transcript.masked_text.find(segment, search_start)
        if segment_index < 0:
            raise ContractError(
                "unclear_segments must come from masked_text in their original order"
            )
        search_start = segment_index + len(segment)

    for segment, replacement_count in Counter(result.unclear_segments).items():
        remaining_limit = transcript.masked_text.count(segment) - replacement_count
        if result.tuned_text.count(segment) > remaining_limit:
            raise ContractError(
                "each unclear segment must be removed where [불명확] replaces it"
            )


def _validate_payload_shape(
    payload: Mapping[str, object],
    *,
    expected_fields: frozenset[str],
    description: str,
) -> None:
    if not isinstance(payload, Mapping):
        raise ContractError(f"{description} must be a JSON object")
    if "raw_text" in payload:
        raise ContractError("raw_text must never be sent to the server")
    if not all(isinstance(key, str) for key in payload):
        raise ContractError(f"{description} field names must be strings")

    actual_fields = set(payload)
    missing_fields = expected_fields - actual_fields
    unexpected_fields = actual_fields - expected_fields

    if missing_fields:
        raise ContractError(
            f"{description} is missing field(s): "
            + ", ".join(sorted(missing_fields))
        )
    if unexpected_fields:
        raise ContractError(
            f"{description} contains unexpected field(s): "
            + ", ".join(sorted(unexpected_fields))
        )


def _validate_schema_version(value: object) -> str:
    version = _require_non_blank_string(value, "schema_version")
    if version != SUPPORTED_SCHEMA_VERSION:
        raise ContractError(
            f"unsupported schema_version: {version!r}; "
            f"expected {SUPPORTED_SCHEMA_VERSION!r}"
        )
    return version


def _validate_conversation_id(value: object) -> str:
    conversation_id = _require_non_blank_string(value, "conversation_id")
    if conversation_id != conversation_id.strip():
        raise ContractError("conversation_id must not have surrounding whitespace")
    if len(conversation_id) > 128:
        raise ContractError("conversation_id must be at most 128 characters")
    return conversation_id


def _require_positive_integer(value: object, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ContractError(f"{field_name} must be a positive integer")
    return value


def _require_boolean(value: object, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ContractError(f"{field_name} must be a boolean")
    return value


def _require_non_blank_string(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"{field_name} must be a non-blank string")
    return value


def _require_string_array(value: object, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ContractError(f"{field_name} must be a JSON array")
    if not all(isinstance(item, str) and item.strip() for item in value):
        raise ContractError(f"{field_name} must contain only non-blank strings")
    return tuple(value)


def _require_string_tuple(value: object, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, tuple):
        raise ContractError(f"{field_name} must be a tuple inside the application")
    if not all(isinstance(item, str) and item.strip() for item in value):
        raise ContractError(f"{field_name} must contain only non-blank strings")
    return value


def _extract_masked_types(
    text: str,
    *,
    allow_unclear: bool = False,
) -> tuple[str, ...]:
    bracketed_tokens = tuple(_BRACKETED_TOKEN_PATTERN.findall(text))
    text_without_tokens = _BRACKETED_TOKEN_PATTERN.sub("", text)
    if "[" in text_without_tokens or "]" in text_without_tokens:
        raise ContractError("masked text contains a malformed bracketed token")

    permitted_tokens = _ALLOWED_MASK_TOKENS
    if allow_unclear:
        permitted_tokens = permitted_tokens | {UNCLEAR_TOKEN}

    unsupported_tokens = set(bracketed_tokens) - permitted_tokens
    if unsupported_tokens:
        raise ContractError(
            "unsupported bracketed token(s): "
            + ", ".join(sorted(unsupported_tokens))
        )

    return tuple(
        token[1:-1] for token in bracketed_tokens if token in _ALLOWED_MASK_TOKENS
    )


def _validate_masked_types(
    masked_types: tuple[str, ...],
    *,
    reject_duplicates: bool = False,
) -> None:
    unsupported_types = set(masked_types) - ALLOWED_MASKED_TYPES
    if unsupported_types:
        raise ContractError(
            "unsupported masking type(s): "
            + ", ".join(sorted(unsupported_types))
        )
    if reject_duplicates and len(masked_types) != len(set(masked_types)):
        raise ContractError("masked_types must not contain duplicates")
