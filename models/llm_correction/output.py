"""Safe, idempotent persistence for validated STT correction results."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, NoReturn

from .contracts import (
    ContractError,
    CorrectionResult,
    MaskedTranscript,
)


MAX_STORED_RESULT_BYTES = 100_000


class CorrectionOutputError(RuntimeError):
    """Raised when a correction result cannot be safely stored or loaded."""


class CorrectionOutputConflictError(CorrectionOutputError):
    """Raised when one conversation/utterance key has conflicting results."""


class _StoredResultFormatError(ValueError):
    """Internal signal for malformed stored JSON without exposing its content."""


class CorrectionResultStore:
    """Store one immutable JSON result per conversation and utterance."""

    def __init__(self, output_root: str | os.PathLike[str]) -> None:
        if isinstance(output_root, str) and not output_root.strip():
            raise ValueError("output_root must not be blank")
        try:
            self._output_root = Path(output_root)
        except TypeError:
            raise TypeError("output_root must be a string or path") from None

    def load(self, transcript: MaskedTranscript) -> CorrectionResult | None:
        """Load an existing result for a validated request, if one exists."""

        if not isinstance(transcript, MaskedTranscript):
            raise TypeError("transcript must be a MaskedTranscript")

        root = self._resolve_existing_root()
        if root is None:
            return None

        conversation_directory = self._conversation_directory(
            root,
            transcript.conversation_id,
        )
        if conversation_directory.is_symlink():
            raise CorrectionOutputError("correction output directory is unsafe")
        if not conversation_directory.exists():
            return None
        if not conversation_directory.is_dir():
            raise CorrectionOutputError("correction output directory is invalid")

        conversation_directory = _resolve_directory(
            conversation_directory,
            "correction output directory",
        )
        if conversation_directory.parent != root:
            raise CorrectionOutputError("correction output directory escaped its root")

        target = conversation_directory / _result_filename(transcript.utterance_id)
        if target.is_symlink():
            raise CorrectionOutputError("stored correction result is unsafe")
        if not target.exists():
            return None
        if not target.is_file():
            raise CorrectionOutputError("stored correction result is invalid")

        existing = _read_result(target)
        if (
            existing.schema_version != transcript.schema_version
            or existing.conversation_id != transcript.conversation_id
            or existing.utterance_id != transcript.utterance_id
        ):
            raise CorrectionOutputConflictError(
                "stored correction result conflicts with the request"
            )
        return existing

    def save(self, result: CorrectionResult) -> Path:
        """Atomically create a result, or return an identical existing result."""

        if not isinstance(result, CorrectionResult):
            raise TypeError("result must be a CorrectionResult")

        root = self._create_and_resolve_root()
        conversation_directory = self._prepare_conversation_directory(
            root,
            result.conversation_id,
        )
        target = conversation_directory / _result_filename(result.utterance_id)

        if target.is_symlink():
            raise CorrectionOutputError("stored correction result is unsafe")
        if target.exists():
            return _return_identical_or_raise_conflict(target, result)

        serialized_result = _serialize_result(result)
        published = _publish_without_overwriting(target, serialized_result)
        if published:
            return target

        return _return_identical_or_raise_conflict(target, result)

    def _resolve_existing_root(self) -> Path | None:
        if self._output_root.is_symlink():
            raise CorrectionOutputError("correction output root is unsafe")
        if not self._output_root.exists():
            return None
        return _resolve_directory(self._output_root, "correction output root")

    def _create_and_resolve_root(self) -> Path:
        creation_failed = False
        try:
            self._output_root.mkdir(parents=True, exist_ok=True)
        except OSError:
            creation_failed = True

        if creation_failed:
            raise CorrectionOutputError("correction output root cannot be created")
        if self._output_root.is_symlink():
            raise CorrectionOutputError("correction output root is unsafe")
        return _resolve_directory(self._output_root, "correction output root")

    @staticmethod
    def _conversation_directory(root: Path, conversation_id: str) -> Path:
        digest = hashlib.sha256(conversation_id.encode("utf-8")).hexdigest()
        return root / f"conversation-{digest}"

    def _prepare_conversation_directory(
        self,
        root: Path,
        conversation_id: str,
    ) -> Path:
        directory = self._conversation_directory(root, conversation_id)
        creation_failed = False
        try:
            directory.mkdir(exist_ok=True)
        except OSError:
            creation_failed = True

        if creation_failed:
            raise CorrectionOutputError(
                "correction output directory cannot be created"
            )
        if directory.is_symlink():
            raise CorrectionOutputError("correction output directory is unsafe")

        resolved_directory = _resolve_directory(
            directory,
            "correction output directory",
        )
        if resolved_directory.parent != root:
            raise CorrectionOutputError("correction output directory escaped its root")
        return resolved_directory


def _result_filename(utterance_id: int) -> str:
    return f"tuned_result{utterance_id:04d}.json"


def _resolve_directory(path: Path, description: str) -> Path:
    resolution_failed = False
    try:
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError):
        resolution_failed = True

    if resolution_failed:
        raise CorrectionOutputError(f"{description} cannot be resolved")
    if not resolved.is_dir():
        raise CorrectionOutputError(f"{description} is not a directory")
    return resolved


def _serialize_result(result: CorrectionResult) -> bytes:
    serialization_failed = False
    try:
        text = json.dumps(
            result.to_dict(),
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
        )
    except (TypeError, ValueError):
        serialization_failed = True

    if serialization_failed:
        raise CorrectionOutputError("correction result cannot be serialized")
    return (text + "\n").encode("utf-8")


def _publish_without_overwriting(target: Path, data: bytes) -> bool:
    """Publish complete bytes with create-if-absent semantics."""

    descriptor = -1
    temporary_path: Path | None = None
    target_already_exists = False
    operation_failed = False

    try:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=".tuned-result-",
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
                # Publication did not depend on this best-effort cleanup.
                pass
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                # A successfully linked final file remains the authoritative result.
                pass

    if operation_failed:
        raise CorrectionOutputError("correction result cannot be stored")
    return not target_already_exists


def _return_identical_or_raise_conflict(
    target: Path,
    result: CorrectionResult,
) -> Path:
    if target.is_symlink() or not target.is_file():
        raise CorrectionOutputError("stored correction result is invalid")

    existing = _read_result(target)
    if existing == result:
        return target
    raise CorrectionOutputConflictError(
        "a different correction result already exists for this request"
    )


def _read_result(path: Path) -> CorrectionResult:
    read_failed = False
    try:
        with path.open("rb") as stored_file:
            encoded = stored_file.read(MAX_STORED_RESULT_BYTES + 1)
    except OSError:
        read_failed = True

    if read_failed:
        raise CorrectionOutputError("stored correction result cannot be read")
    if len(encoded) > MAX_STORED_RESULT_BYTES:
        raise CorrectionOutputError("stored correction result exceeds the size limit")

    decode_failed = False
    try:
        text = encoded.decode("utf-8")
    except UnicodeError:
        decode_failed = True

    if decode_failed:
        raise CorrectionOutputError("stored correction result is not UTF-8")

    parse_failed = False
    try:
        payload = json.loads(
            text,
            object_pairs_hook=_object_without_duplicate_keys,
            parse_constant=_reject_non_standard_json_constant,
        )
    except (json.JSONDecodeError, RecursionError, _StoredResultFormatError):
        parse_failed = True

    if parse_failed:
        raise CorrectionOutputError("stored correction result is not valid JSON")

    validation_failed = False
    try:
        result = CorrectionResult.from_dict(payload)
    except (ContractError, TypeError):
        validation_failed = True

    if validation_failed:
        raise CorrectionOutputError("stored correction result violates the contract")
    return result


def _object_without_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key, value in pairs:
        if key in payload:
            raise _StoredResultFormatError
        payload[key] = value
    return payload


def _reject_non_standard_json_constant(_value: str) -> NoReturn:
    raise _StoredResultFormatError
