"""Atomic, idempotent storage for conversation-context snapshots."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NoReturn

from models.context_manager import ConversationContext, Utterance, merge_utterance
from models.context_manager.loader import InputDataError
from models.llm_correction import (
    ContractError,
    CorrectionResult,
    MaskedTranscript,
    validate_correction_against_input,
)


MAX_STORED_CONTEXT_BYTES = 1_000_000
_CONTEXT_FILENAME_PATTERN = re.compile(r"^context_result([0-9]+)\.json$")
_CONTEXT_FIELDS = frozenset({"current", "history"})
_UTTERANCE_FIELDS = frozenset(
    {
        "schema_version",
        "conversation_id",
        "utterance_id",
        "masked_text",
        "has_masked_data",
        "masked_types",
        "tuned_text",
        "is_tuned",
        "has_unclear",
        "unclear_segments",
    }
)


class ContextOutputError(RuntimeError):
    """Raised when a context snapshot cannot be safely stored or loaded."""


class ContextOutputConflictError(ContextOutputError):
    """Raised when one conversation/utterance key has conflicting contexts."""


class _StoredContextFormatError(ValueError):
    pass


@dataclass(frozen=True)
class StoredConversationContext:
    context: ConversationContext
    path: Path


class ContextResultStore:
    """Store an immutable context snapshot for every accepted utterance."""

    def __init__(self, output_root: str | os.PathLike[str]) -> None:
        if isinstance(output_root, str) and not output_root.strip():
            raise ValueError("output_root must not be blank")
        try:
            self._output_root = Path(output_root)
        except TypeError:
            raise TypeError("output_root must be a string or path") from None

    def load(
        self,
        conversation_id: str,
        utterance_id: int,
    ) -> StoredConversationContext | None:
        _validate_lookup_key(conversation_id, utterance_id)
        root = self._resolve_existing_root()
        if root is None:
            return None

        directory = self._resolve_existing_conversation_directory(
            root,
            conversation_id,
        )
        if directory is None:
            return None

        target = directory / _context_filename(utterance_id)
        if target.is_symlink():
            raise ContextOutputError("stored context result is unsafe")
        if not target.exists():
            return None
        if not target.is_file():
            raise ContextOutputError("stored context result is invalid")

        context = _read_context(target)
        _validate_context_key(context, conversation_id, utterance_id)
        return StoredConversationContext(context=context, path=target)

    def load_latest(
        self,
        conversation_id: str,
    ) -> StoredConversationContext | None:
        if not isinstance(conversation_id, str) or not conversation_id.strip():
            raise ValueError("conversation_id must be a non-blank string")
        root = self._resolve_existing_root()
        if root is None:
            return None

        directory = self._resolve_existing_conversation_directory(
            root,
            conversation_id,
        )
        if directory is None:
            return None

        candidates: list[tuple[int, Path]] = []
        try:
            children = list(directory.iterdir())
        except OSError:
            raise ContextOutputError("context output directory cannot be read") from None

        for child in children:
            match = _CONTEXT_FILENAME_PATTERN.fullmatch(child.name)
            if match is None:
                continue
            if child.is_symlink() or not child.is_file():
                raise ContextOutputError("stored context result is invalid")
            candidates.append((int(match.group(1)), child))

        if not candidates:
            return None
        utterance_id, target = max(candidates, key=lambda item: item[0])
        context = _read_context(target)
        _validate_context_key(context, conversation_id, utterance_id)
        return StoredConversationContext(context=context, path=target)

    def save(self, context: ConversationContext) -> Path:
        if not isinstance(context, ConversationContext):
            raise TypeError("context must be a ConversationContext")
        validated = _context_from_payload(context.to_dict())
        if validated.to_dict() != context.to_dict():
            raise ContextOutputError("conversation context changed during validation")

        current = validated.current
        root = self._create_and_resolve_root()
        directory = self._prepare_conversation_directory(
            root,
            current.conversation_id,
        )
        target = directory / _context_filename(current.utterance_id)
        if target.is_symlink():
            raise ContextOutputError("stored context result is unsafe")
        if target.exists():
            return _return_identical_or_raise_conflict(target, validated)

        data = _serialize_context(validated)
        published = _publish_without_overwriting(target, data)
        if published:
            return target
        return _return_identical_or_raise_conflict(target, validated)

    def relative_key(self, path: Path) -> str:
        root = self._resolve_existing_root()
        if root is None:
            raise ContextOutputError("context output root does not exist")
        try:
            resolved_path = path.resolve(strict=True)
            key = resolved_path.relative_to(root.parent)
        except (OSError, RuntimeError, ValueError):
            raise ContextOutputError("stored context path escaped its data root") from None
        return key.as_posix()

    def _resolve_existing_root(self) -> Path | None:
        if self._output_root.is_symlink():
            raise ContextOutputError("context output root is unsafe")
        if not self._output_root.exists():
            return None
        return _resolve_directory(self._output_root, "context output root")

    def _create_and_resolve_root(self) -> Path:
        try:
            self._output_root.mkdir(parents=True, exist_ok=True)
        except OSError:
            raise ContextOutputError("context output root cannot be created") from None
        if self._output_root.is_symlink():
            raise ContextOutputError("context output root is unsafe")
        return _resolve_directory(self._output_root, "context output root")

    @staticmethod
    def _conversation_directory(root: Path, conversation_id: str) -> Path:
        digest = hashlib.sha256(conversation_id.encode("utf-8")).hexdigest()
        return root / f"conversation-{digest}"

    def _resolve_existing_conversation_directory(
        self,
        root: Path,
        conversation_id: str,
    ) -> Path | None:
        directory = self._conversation_directory(root, conversation_id)
        if directory.is_symlink():
            raise ContextOutputError("context output directory is unsafe")
        if not directory.exists():
            return None
        resolved = _resolve_directory(directory, "context output directory")
        if resolved.parent != root:
            raise ContextOutputError("context output directory escaped its root")
        return resolved

    def _prepare_conversation_directory(
        self,
        root: Path,
        conversation_id: str,
    ) -> Path:
        directory = self._conversation_directory(root, conversation_id)
        try:
            directory.mkdir(exist_ok=True)
        except OSError:
            raise ContextOutputError(
                "context output directory cannot be created"
            ) from None
        if directory.is_symlink():
            raise ContextOutputError("context output directory is unsafe")
        resolved = _resolve_directory(directory, "context output directory")
        if resolved.parent != root:
            raise ContextOutputError("context output directory escaped its root")
        return resolved


def _validate_lookup_key(conversation_id: object, utterance_id: object) -> None:
    if not isinstance(conversation_id, str) or not conversation_id.strip():
        raise ValueError("conversation_id must be a non-blank string")
    if (
        not isinstance(utterance_id, int)
        or isinstance(utterance_id, bool)
        or utterance_id < 1
    ):
        raise ValueError("utterance_id must be a positive integer")


def _context_filename(utterance_id: int) -> str:
    return f"context_result{utterance_id:04d}.json"


def _resolve_directory(path: Path, description: str) -> Path:
    try:
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError):
        raise ContextOutputError(f"{description} cannot be resolved") from None
    if not resolved.is_dir():
        raise ContextOutputError(f"{description} is not a directory")
    return resolved


def _serialize_context(context: ConversationContext) -> bytes:
    try:
        text = json.dumps(
            context.to_dict(),
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
        )
    except (TypeError, ValueError):
        raise ContextOutputError("conversation context cannot be serialized") from None
    return (text + "\n").encode("utf-8")


def _publish_without_overwriting(target: Path, data: bytes) -> bool:
    descriptor = -1
    temporary_path: Path | None = None
    target_already_exists = False
    operation_failed = False
    try:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=".context-result-",
            suffix=".tmp",
            dir=target.parent,
        )
        temporary_path = Path(temporary_name)
        temporary_file = os.fdopen(descriptor, "wb")
        descriptor = -1
        with temporary_file:
            temporary_file.write(data)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        try:
            os.link(temporary_path, target)
        except FileExistsError:
            target_already_exists = True
        except OSError:
            operation_failed = True
    except OSError:
        operation_failed = True
    finally:
        if descriptor >= 0:
            try:
                os.close(descriptor)
            except OSError:
                pass
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass

    if operation_failed:
        raise ContextOutputError("conversation context cannot be stored")
    return not target_already_exists


def _return_identical_or_raise_conflict(
    target: Path,
    context: ConversationContext,
) -> Path:
    if target.is_symlink() or not target.is_file():
        raise ContextOutputError("stored context result is invalid")
    existing = _read_context(target)
    if existing.to_dict() == context.to_dict():
        return target
    raise ContextOutputConflictError(
        "a different context already exists for this request"
    )


def _read_context(path: Path) -> ConversationContext:
    try:
        with path.open("rb") as stored_file:
            encoded = stored_file.read(MAX_STORED_CONTEXT_BYTES + 1)
    except OSError:
        raise ContextOutputError("stored context result cannot be read") from None
    if len(encoded) > MAX_STORED_CONTEXT_BYTES:
        raise ContextOutputError("stored context result exceeds the size limit")

    try:
        text = encoded.decode("utf-8")
    except UnicodeError:
        raise ContextOutputError("stored context result is not UTF-8") from None

    try:
        payload = json.loads(
            text,
            object_pairs_hook=_object_without_duplicate_keys,
            parse_constant=_reject_non_standard_json_constant,
        )
        return _context_from_payload(payload)
    except (
        json.JSONDecodeError,
        RecursionError,
        _StoredContextFormatError,
        ContractError,
        InputDataError,
        KeyError,
        TypeError,
        ValueError,
    ):
        raise ContextOutputError(
            "stored context result violates the contract"
        ) from None


def _context_from_payload(payload: object) -> ConversationContext:
    if not isinstance(payload, Mapping) or set(payload) != _CONTEXT_FIELDS:
        raise _StoredContextFormatError
    current = _utterance_from_payload(payload["current"])
    history_payload = payload["history"]
    if not isinstance(history_payload, list):
        raise _StoredContextFormatError
    history = [_utterance_from_payload(item) for item in history_payload]

    all_items = [*history, current]
    if any(item.conversation_id != current.conversation_id for item in all_items):
        raise _StoredContextFormatError
    if any(item.schema_version != current.schema_version for item in all_items):
        raise _StoredContextFormatError
    ordered_ids = [item.utterance_id for item in all_items]
    if ordered_ids != sorted(set(ordered_ids)):
        raise _StoredContextFormatError
    return ConversationContext(current=current, history=history)


def _utterance_from_payload(payload: object) -> Utterance:
    if not isinstance(payload, Mapping) or set(payload) != _UTTERANCE_FIELDS:
        raise _StoredContextFormatError
    masked_payload = {
        field: payload[field]
        for field in (
            "schema_version",
            "conversation_id",
            "utterance_id",
            "masked_text",
            "has_masked_data",
            "masked_types",
        )
    }
    tuned_payload = {
        field: payload[field]
        for field in (
            "schema_version",
            "conversation_id",
            "utterance_id",
            "tuned_text",
            "is_tuned",
            "has_unclear",
            "unclear_segments",
        )
    }
    transcript = MaskedTranscript.from_dict(masked_payload)
    result = CorrectionResult.from_dict(tuned_payload)
    validate_correction_against_input(transcript, result)
    return merge_utterance(masked_payload, tuned_payload)


def _validate_context_key(
    context: ConversationContext,
    conversation_id: str,
    utterance_id: int,
) -> None:
    if (
        context.current.conversation_id != conversation_id
        or context.current.utterance_id != utterance_id
    ):
        raise ContextOutputConflictError(
            "stored context result conflicts with its filename"
        )


def _object_without_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key, value in pairs:
        if key in payload:
            raise _StoredContextFormatError
        payload[key] = value
    return payload


def _reject_non_standard_json_constant(_value: str) -> NoReturn:
    raise _StoredContextFormatError
