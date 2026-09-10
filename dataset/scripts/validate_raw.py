#!/usr/bin/env python3
"""Validate raw utterance JSON files without third-party dependencies."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


ID_PATTERN = re.compile(r"^[PN]\d{4}$")
FILENAME_PATTERN = re.compile(r"^utterance_(\d+)\.json$")
REQUIRED_FIELDS = ("conversation_id", "utterance_id", "speaker", "text", "source")
VALID_SPEAKERS = {"speaker_A", "speaker_B", "unknown"}


def add_issue(issues: list[str], path: Path, message: str) -> None:
    issues.append(f"{path}: {message}")


def validate_file(path: Path, raw_root: Path, errors: list[str]) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError:
        add_issue(errors, path, "file is not valid UTF-8")
        return None
    except json.JSONDecodeError as exc:
        add_issue(errors, path, f"invalid JSON ({exc.msg}, line {exc.lineno}, column {exc.colno})")
        return None

    if not isinstance(payload, dict):
        add_issue(errors, path, "JSON root must be an object")
        return None

    for field in REQUIRED_FIELDS:
        if field not in payload:
            add_issue(errors, path, f"missing required field '{field}'")

    if any(field not in payload for field in REQUIRED_FIELDS):
        return None

    conversation_id = payload["conversation_id"]
    utterance_id = payload["utterance_id"]
    speaker = payload["speaker"]
    text = payload["text"]
    source = payload["source"]
    valid = True

    if not isinstance(conversation_id, str) or not ID_PATTERN.fullmatch(conversation_id):
        add_issue(errors, path, "conversation_id must match ^[PN]\\d{4}$")
        valid = False
    if isinstance(utterance_id, bool) or not isinstance(utterance_id, int) or utterance_id < 1:
        add_issue(errors, path, "utterance_id must be an integer of at least 1")
        valid = False
    if speaker not in VALID_SPEAKERS:
        add_issue(errors, path, "speaker must be one of speaker_A, speaker_B, unknown")
        valid = False
    if not isinstance(text, str) or not text.strip():
        add_issue(errors, path, "text must be a non-empty, non-whitespace string")
        valid = False
    if not isinstance(source, str) or not source.strip():
        add_issue(errors, path, "source must be a non-empty string")
        valid = False

    try:
        relative = path.relative_to(raw_root)
        category, folder_id, filename = relative.parts
    except ValueError:
        add_issue(errors, path, "file is outside the raw data directory")
        return None
    except ValueError:
        return None

    if len(relative.parts) != 3 or category not in {"phishing", "normal"}:
        add_issue(errors, path, "expected path raw/(phishing|normal)/<conversation_id>/utterance_NNN.json")
        valid = False
    else:
        expected_prefix = "P" if category == "phishing" else "N"
        if isinstance(conversation_id, str) and folder_id != conversation_id:
            add_issue(errors, path, f"folder ID '{folder_id}' does not match conversation_id '{conversation_id}'")
            valid = False
        if isinstance(conversation_id, str) and not conversation_id.startswith(expected_prefix):
            add_issue(errors, path, f"conversation_id prefix must be '{expected_prefix}' under '{category}'")
            valid = False
        match = FILENAME_PATTERN.fullmatch(filename)
        if not match:
            add_issue(errors, path, "filename must match utterance_NNN.json")
            valid = False
        elif isinstance(utterance_id, int) and not isinstance(utterance_id, bool) and int(match.group(1)) != utterance_id:
            add_issue(errors, path, f"filename utterance number {int(match.group(1))} does not match utterance_id {utterance_id}")
            valid = False

    return payload if valid else None


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate dataset/raw utterance JSON files.")
    parser.add_argument("raw_dir", nargs="?", type=Path, default=Path(__file__).resolve().parents[1] / "raw")
    args = parser.parse_args()
    raw_root = args.raw_dir.resolve()
    errors: list[str] = []
    warnings: list[str] = []
    conversations: dict[str, list[tuple[Path, dict[str, Any]]]] = defaultdict(list)
    records: dict[tuple[Any, ...], Path] = {}

    if not raw_root.is_dir():
        print(f"Error: raw data directory does not exist: {raw_root}")
        return 1

    files = sorted(raw_root.rglob("*.json"))
    for path in files:
        payload = validate_file(path, raw_root, errors)
        if payload is None:
            continue
        key = tuple(payload[field] for field in REQUIRED_FIELDS)
        if key in records:
            add_issue(errors, path, f"duplicate record; first seen in {records[key]}")
            continue
        records[key] = path
        conversations[payload["conversation_id"]].append((path, payload))

    for conversation_id, entries in sorted(conversations.items()):
        seen_ids: dict[int, Path] = {}
        for path, payload in entries:
            utterance_id = payload["utterance_id"]
            if utterance_id in seen_ids:
                add_issue(errors, path, f"duplicate utterance_id {utterance_id} in {conversation_id}; first seen in {seen_ids[utterance_id]}")
            else:
                seen_ids[utterance_id] = path
        expected = list(range(1, len(seen_ids) + 1))
        actual = sorted(seen_ids)
        if actual != expected:
            warnings.append(f"{conversation_id}: utterance IDs are not consecutive from 1 (found: {actual})")

    for issue in errors:
        print(f"ERROR: {issue}")
    for issue in warnings:
        print(f"WARNING: {issue}")
    print(f"Validated conversations: {len(conversations)}")
    print(f"Validated utterances: {sum(len(entries) for entries in conversations.values())}")
    print(f"Errors: {len(errors)}")
    print(f"Warnings: {len(warnings)}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
