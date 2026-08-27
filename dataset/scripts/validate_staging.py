#!/usr/bin/env python3
"""Validate labeled JSONL files in dataset/staging without third-party dependencies."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ID_PATTERN = re.compile(r"^[PN]\d{4}$")
VALID_SPEAKERS = {"speaker_A", "speaker_B", "unknown"}
VALID_LABELS = {
    "institution_impersonation",
    "money_transfer",
    "personal_information",
    "app_installation",
    "secrecy",
    "threat_pressure",
}
DATA_FIELDS = (
    "conversation_id",
    "utterance_id",
    "speaker",
    "text",
    "source",
    "is_phishing",
    "labels",
)
REVIEW_FIELDS = (
    "conversation_id",
    "utterance_id",
    "text",
    "provisional_is_phishing",
    "provisional_labels",
    "reason",
    "status",
)


def location(path: Path, line_number: int) -> str:
    return f"{path}:{line_number}"


def load_jsonl(path: Path, errors: list[str]) -> list[tuple[int, dict[str, Any]]]:
    rows: list[tuple[int, dict[str, Any]]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        errors.append(f"{path}: file is not valid UTF-8")
        return rows

    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(
                f"{location(path, line_number)}: invalid JSON "
                f"({exc.msg}, column {exc.colno})"
            )
            continue
        if not isinstance(payload, dict):
            errors.append(f"{location(path, line_number)}: JSON value must be an object")
            continue
        rows.append((line_number, payload))
    return rows


def valid_key(payload: dict[str, Any], where: str, errors: list[str]) -> tuple[str, int] | None:
    conversation_id = payload.get("conversation_id")
    utterance_id = payload.get("utterance_id")
    if not isinstance(conversation_id, str) or not ID_PATTERN.fullmatch(conversation_id):
        errors.append(f"{where}: conversation_id must match ^[PN]\\d{{4}}$")
        return None
    if isinstance(utterance_id, bool) or not isinstance(utterance_id, int) or utterance_id < 1:
        errors.append(f"{where}: utterance_id must be an integer of at least 1")
        return None
    return conversation_id, utterance_id


def validate_labels(labels: Any, where: str, field: str, errors: list[str]) -> bool:
    if not isinstance(labels, list):
        errors.append(f"{where}: {field} must be a list")
        return False
    if len(labels) != len(set(label for label in labels if isinstance(label, str))):
        errors.append(f"{where}: {field} contains duplicate values")
    for label in labels:
        if not isinstance(label, str) or label not in VALID_LABELS:
            errors.append(f"{where}: unsupported label in {field}: {label!r}")
    return True


def load_raw(raw_dir: Path, errors: list[str]) -> dict[tuple[str, int], dict[str, Any]]:
    records: dict[tuple[str, int], dict[str, Any]] = {}
    for path in sorted(raw_dir.rglob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            errors.append(f"{path}: unable to read raw JSON ({exc})")
            continue
        if not isinstance(payload, dict):
            errors.append(f"{path}: raw JSON root must be an object")
            continue
        key = valid_key(payload, str(path), errors)
        if key is None:
            continue
        if key in records:
            errors.append(f"{path}: duplicate raw key {key[0]}-{key[1]}")
            continue
        records[key] = payload
    return records


def main() -> int:
    dataset_dir = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Validate dataset/staging JSONL files.")
    parser.add_argument("staging_dir", nargs="?", type=Path, default=dataset_dir / "staging")
    parser.add_argument("--raw-dir", type=Path, default=dataset_dir / "raw")
    args = parser.parse_args()

    staging_dir = args.staging_dir.resolve()
    raw_dir = args.raw_dir.resolve()
    errors: list[str] = []
    warnings: list[str] = []

    if not staging_dir.is_dir():
        print(f"Error: staging directory does not exist: {staging_dir}")
        return 1
    if not raw_dir.is_dir():
        print(f"Error: raw directory does not exist: {raw_dir}")
        return 1

    raw_records = load_raw(raw_dir, errors)
    data_files = sorted(
        path for path in staging_dir.glob("*.jsonl") if not path.name.startswith("review_queue_")
    )
    review_files = sorted(staging_dir.glob("review_queue_*.jsonl"))
    if not data_files:
        errors.append(f"{staging_dir}: no labeled data JSONL files found")
    if not review_files:
        warnings.append(f"{staging_dir}: no review_queue JSONL files found")

    data_records: dict[tuple[str, int], tuple[Path, int, dict[str, Any]]] = {}
    true_without_labels: set[tuple[str, int]] = set()
    phishing_counts = Counter()
    label_counts = Counter()

    for path in data_files:
        for line_number, payload in load_jsonl(path, errors):
            where = location(path, line_number)
            missing = [field for field in DATA_FIELDS if field not in payload]
            if missing:
                errors.append(f"{where}: missing required fields: {', '.join(missing)}")
                continue
            key = valid_key(payload, where, errors)
            if key is None:
                continue
            if key in data_records:
                first_path, first_line, _ = data_records[key]
                errors.append(
                    f"{where}: duplicate labeled ID {key[0]}-{key[1]}; "
                    f"first seen at {location(first_path, first_line)}"
                )
                continue

            speaker = payload["speaker"]
            text = payload["text"]
            source = payload["source"]
            is_phishing = payload["is_phishing"]
            labels = payload["labels"]
            if speaker not in VALID_SPEAKERS:
                errors.append(f"{where}: speaker must be speaker_A, speaker_B, or unknown")
            if not isinstance(text, str) or not text.strip():
                errors.append(f"{where}: text must be a non-empty string")
            if not isinstance(source, str) or not source.strip():
                errors.append(f"{where}: source must be a non-empty string")
            if not isinstance(is_phishing, bool):
                errors.append(f"{where}: is_phishing must be true or false")
            labels_valid = validate_labels(labels, where, "labels", errors)
            if isinstance(is_phishing, bool) and labels_valid:
                phishing_counts[is_phishing] += 1
                if not is_phishing and labels:
                    errors.append(f"{where}: is_phishing=false requires labels=[]")
                if is_phishing and not labels:
                    true_without_labels.add(key)
                label_counts.update(labels)

            raw = raw_records.get(key)
            if raw is None:
                errors.append(f"{where}: labeled ID {key[0]}-{key[1]} does not exist in raw")
            else:
                for field in ("speaker", "text", "source"):
                    if payload[field] != raw.get(field):
                        errors.append(f"{where}: {field} does not match raw")
            data_records[key] = (path, line_number, payload)

    review_records: dict[tuple[str, int], tuple[Path, int, dict[str, Any]]] = {}
    for path in review_files:
        for line_number, payload in load_jsonl(path, errors):
            where = location(path, line_number)
            missing = [field for field in REVIEW_FIELDS if field not in payload]
            if missing:
                errors.append(f"{where}: missing required fields: {', '.join(missing)}")
                continue
            key = valid_key(payload, where, errors)
            if key is None:
                continue
            if key in review_records:
                first_path, first_line, _ = review_records[key]
                errors.append(
                    f"{where}: duplicate review ID {key[0]}-{key[1]}; "
                    f"first seen at {location(first_path, first_line)}"
                )
                continue
            if key not in data_records:
                errors.append(f"{where}: review ID {key[0]}-{key[1]} is absent from labeled data")
            elif payload["text"] != data_records[key][2]["text"]:
                errors.append(f"{where}: review text does not match labeled data")
            if not isinstance(payload["provisional_is_phishing"], bool):
                errors.append(f"{where}: provisional_is_phishing must be true or false")
            validate_labels(payload["provisional_labels"], where, "provisional_labels", errors)
            if not isinstance(payload["reason"], str) or not payload["reason"].strip():
                errors.append(f"{where}: reason must be a non-empty string")
            if payload["status"] != "needs_review":
                errors.append(f"{where}: status must be 'needs_review'")
            review_records[key] = (path, line_number, payload)

    missing_review = sorted(true_without_labels - set(review_records))
    for conversation_id, utterance_id in missing_review:
        errors.append(
            f"staging: is_phishing=true and labels=[] record "
            f"{conversation_id}-{utterance_id} is missing from review queue"
        )

    missing_labeled = sorted(set(raw_records) - set(data_records))
    for conversation_id, utterance_id in missing_labeled:
        errors.append(f"staging: raw record {conversation_id}-{utterance_id} is missing from labeled data")

    for issue in errors:
        print(f"ERROR: {issue}")
    for issue in warnings:
        print(f"WARNING: {issue}")
    print(f"Validated labeled conversations: {len({key[0] for key in data_records})}")
    print(f"Validated labeled utterances: {len(data_records)}")
    print(f"is_phishing=true: {phishing_counts[True]}")
    print(f"is_phishing=false: {phishing_counts[False]}")
    for label in sorted(VALID_LABELS):
        print(f"Label {label}: {label_counts[label]}")
    print(f"Review entries: {len(review_records)}")
    print(f"True-without-label review omissions: {len(missing_review)}")
    print(f"Errors: {len(errors)}")
    print(f"Warnings: {len(warnings)}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
