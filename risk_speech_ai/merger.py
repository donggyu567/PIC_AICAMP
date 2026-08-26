"""Merge task 1 masked output with task 2 correction output."""

from __future__ import annotations

from typing import Any, Mapping

from .loader import InputDataError, validate_masked_result, validate_tuned_result
from .schemas import Utterance


def merge_utterance(
    masked_result: Mapping[str, Any],
    tuned_result: Mapping[str, Any],
) -> Utterance:
    """Merge task 1 and task 2 values that identify the same utterance."""

    validated_masked = validate_masked_result(masked_result)
    validated_tuned = validate_tuned_result(tuned_result)

    if validated_masked["schema_version"] != validated_tuned["schema_version"]:
        raise InputDataError(
            "masked result schema_version does not match tuned result schema_version"
        )
    if validated_masked["conversation_id"] != validated_tuned["conversation_id"]:
        raise InputDataError(
            "masked result conversation_id does not match tuned result conversation_id"
        )
    if validated_masked["utterance_id"] != validated_tuned["utterance_id"]:
        raise InputDataError(
            "masked result utterance_id does not match tuned result utterance_id"
        )

    return Utterance(
        schema_version=validated_masked["schema_version"],
        conversation_id=validated_masked["conversation_id"],
        utterance_id=validated_masked["utterance_id"],
        masked_text=validated_masked["masked_text"],
        has_masked_data=validated_masked["has_masked_data"],
        masked_types=list(validated_masked["masked_types"]),
        tuned_text=validated_tuned["tuned_text"],
        is_tuned=validated_tuned["is_tuned"],
        has_unclear=validated_tuned["has_unclear"],
        unclear_segments=list(validated_tuned["unclear_segments"]),
    )
