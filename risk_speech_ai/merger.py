"""Merge task 1 raw STT text with task 2 correction results."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Mapping

from .loader import (
    InputDataError,
    load_stt_text,
    load_tuned_result,
    validate_tuned_result,
)
from .schemas import Utterance


def extract_utterance_id_from_stt_filename(path: str | Path) -> int:
    """Extract an ID only from the explicit ``result00xx.txt`` filename pattern.

    This helper is optional because a raw STT file does not itself contain an
    ID. Callers with a different source of truth should pass that ID directly
    to :func:`merge_utterance` instead.
    """

    match = re.fullmatch(r"result(\d+)\.txt", Path(path).name)
    if match is None:
        raise InputDataError(
            "cannot extract utterance_id: expected a filename like result0004.txt"
        )
    return int(match.group(1))


def load_utterance(raw_path: str | Path, tuned_path: str | Path) -> Utterance:
    """Load task 1 and task 2 files, verify their IDs, and merge one utterance.

    The raw file must use the explicit ``result00xx.txt`` pattern so its ID can
    be verified. The tuned result is read from its caller-provided path, which
    conventionally uses a name such as ``tuned_result0004.json``.
    """

    raw_text = load_stt_text(raw_path)
    raw_utterance_id = extract_utterance_id_from_stt_filename(raw_path)
    tuned_result = load_tuned_result(tuned_path)
    return merge_utterance(
        raw_text,
        tuned_result,
        raw_utterance_id=raw_utterance_id,
    )


def merge_utterance(
    raw_text: str,
    tuned_result: Mapping[str, Any],
    *,
    raw_utterance_id: int | None = None,
) -> Utterance:
    """Create one utterance while preserving task 1 and task 2 values.

    If a caller has a verifiable raw-source ID, it can be supplied to detect a
    mismatch with task 2. No ID is inferred from arbitrary filenames.
    """

    if not isinstance(raw_text, str):
        raise InputDataError("raw_text must be a string")

    validated_result = validate_tuned_result(tuned_result)
    tuned_utterance_id = validated_result["utterance_id"]

    if raw_utterance_id is not None:
        if not isinstance(raw_utterance_id, int) or isinstance(raw_utterance_id, bool):
            raise InputDataError("raw_utterance_id must be an integer or None")
        if raw_utterance_id != tuned_utterance_id:
            raise InputDataError(
                "raw_utterance_id does not match tuned result utterance_id"
            )

    return Utterance(
        utterance_id=tuned_utterance_id,
        raw_text=raw_text,
        tuned_text=validated_result["tuned_text"],
        is_tuned=validated_result["is_tuned"],
        has_unclear=validated_result["has_unclear"],
        unclear_segments=list(validated_result["unclear_segments"]),
    )
