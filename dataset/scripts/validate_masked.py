#!/usr/bin/env python3
"""Validate masked JSONL files and their review queue."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


DATA_FIELDS = {
    "conversation_id",
    "utterance_id",
    "speaker",
    "text",
    "is_phishing",
    "labels",
    "source",
}
REVIEW_FIELDS = {
    "conversation_id",
    "utterance_id",
    "text",
    "provisional_is_phishing",
    "provisional_labels",
    "reason",
    "status",
}
ALLOWED_LABELS = {
    "institution_impersonation",
    "money_transfer",
    "personal_information",
    "app_installation",
    "secrecy",
    "threat_pressure",
    "loan_fraud",
    "information_probing",
}
ALLOWED_TOKENS = {
    "PERSON",
    "PHONE_NUMBER",
    "ACCOUNT_NUMBER",
    "CARD_NUMBER",
    "ADDRESS",
    "RRN",
    "BIRTH",
    "EMAIL",
    "PW",
}
VALID_SPEAKERS = {"speaker_A", "speaker_B", "unknown"}
ID_PATTERN = re.compile(r"^[PN]\d{4}$")
TOKEN_PATTERN = re.compile(r"\[([A-Z_]+)\]")


def load_jsonl(path: Path, errors: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        errors.append(f"{path}: cannot read UTF-8 JSONL ({exc})")
        return rows
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            errors.append(f"{path}:{line_number}: blank line")
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"{path}:{line_number}: invalid JSON ({exc.msg})")
            continue
        if not isinstance(row, dict):
            errors.append(f"{path}:{line_number}: JSON root must be an object")
            continue
        row["__location"] = f"{path}:{line_number}"
        rows.append(row)
    return rows


def validate_data_row(row: dict[str, Any], errors: list[str]) -> None:
    location = row["__location"]
    fields = set(row) - {"__location"}
    if fields != DATA_FIELDS:
        missing = sorted(DATA_FIELDS - fields)
        extra = sorted(fields - DATA_FIELDS)
        errors.append(f"{location}: field mismatch; missing={missing}, extra={extra}")
        return

    conversation_id = row["conversation_id"]
    utterance_id = row["utterance_id"]
    labels = row["labels"]
    if not isinstance(conversation_id, str) or not ID_PATTERN.fullmatch(conversation_id):
        errors.append(f"{location}: invalid conversation_id")
    if isinstance(utterance_id, bool) or not isinstance(utterance_id, int) or utterance_id < 1:
        errors.append(f"{location}: utterance_id must be an integer of at least 1")
    if row["speaker"] not in VALID_SPEAKERS:
        errors.append(f"{location}: invalid speaker")
    if not isinstance(row["text"], str) or not row["text"].strip():
        errors.append(f"{location}: text must be a non-empty string")
    if not isinstance(row["source"], str) or not row["source"].strip():
        errors.append(f"{location}: source must be a non-empty string")
    if not isinstance(row["is_phishing"], bool):
        errors.append(f"{location}: is_phishing must be boolean")
    if not isinstance(labels, list) or any(not isinstance(label, str) for label in labels):
        errors.append(f"{location}: labels must be a list of strings")
        return
    unknown = sorted(set(labels) - ALLOWED_LABELS)
    if unknown:
        errors.append(f"{location}: unknown labels {unknown}")
    if len(labels) != len(set(labels)):
        errors.append(f"{location}: duplicate labels")
    if row["is_phishing"] is False and labels:
        errors.append(f"{location}: is_phishing=false must have labels=[]")
    unknown_tokens = sorted(set(TOKEN_PATTERN.findall(row["text"])) - ALLOWED_TOKENS)
    if unknown_tokens:
        errors.append(f"{location}: unknown masking tokens {unknown_tokens}")


def validate_review_row(
    row: dict[str, Any], data_by_id: dict[tuple[str, int], dict[str, Any]], errors: list[str]
) -> None:
    location = row["__location"]
    fields = set(row) - {"__location"}
    if fields != REVIEW_FIELDS:
        missing = sorted(REVIEW_FIELDS - fields)
        extra = sorted(fields - REVIEW_FIELDS)
        errors.append(f"{location}: review field mismatch; missing={missing}, extra={extra}")
        return
    key = (row["conversation_id"], row["utterance_id"])
    data = data_by_id.get(key)
    if data is None:
        errors.append(f"{location}: review target {key} not found in masked data")
        return
    if row["text"] != data["text"]:
        errors.append(f"{location}: review text differs from masked data")
    if row["provisional_is_phishing"] != data["is_phishing"]:
        errors.append(f"{location}: provisional_is_phishing differs from masked data")
    if row["provisional_labels"] != data["labels"]:
        errors.append(f"{location}: provisional_labels differs from masked data")
    if not isinstance(row["reason"], str) or not row["reason"].strip():
        errors.append(f"{location}: reason must be a non-empty string")
    if row["status"] != "needs_review":
        errors.append(f"{location}: status must be needs_review")
    if data["is_phishing"] and data["labels"]:
        errors.append(f"{location}: labeled phishing utterance must not remain in review queue")


def compare_staging(
    masked_rows: list[dict[str, Any]], staging_paths: list[Path], errors: list[str]
) -> None:
    if not staging_paths:
        return
    staging_rows: list[dict[str, Any]] = []
    for path in staging_paths:
        staging_rows.extend(load_jsonl(path, errors))
    staging_by_id = {
        (row.get("conversation_id"), row.get("utterance_id")): row for row in staging_rows
    }
    masked_by_id = {
        (row.get("conversation_id"), row.get("utterance_id")): row for row in masked_rows
    }
    if set(staging_by_id) != set(masked_by_id):
        errors.append("masked and staging utterance ID sets differ")
        return
    for key, masked in masked_by_id.items():
        staging = staging_by_id[key]
        for field in ("conversation_id", "utterance_id", "speaker", "is_phishing", "source"):
            if masked[field] != staging[field]:
                errors.append(f"{key}: '{field}' differs from staging")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("masked", nargs="+", type=Path, help="masked data JSONL files")
    parser.add_argument("--review", type=Path, required=True, help="masked review queue JSONL")
    parser.add_argument("--staging", nargs="*", type=Path, default=[], help="source staging JSONL files")
    args = parser.parse_args()

    errors: list[str] = []
    data_rows: list[dict[str, Any]] = []
    for path in args.masked:
        data_rows.extend(load_jsonl(path, errors))
    for row in data_rows:
        validate_data_row(row, errors)

    data_by_id: dict[tuple[str, int], dict[str, Any]] = {}
    duplicate_ids = 0
    conversations: dict[str, list[int]] = defaultdict(list)
    for row in data_rows:
        key = (row.get("conversation_id"), row.get("utterance_id"))
        if key in data_by_id:
            duplicate_ids += 1
            errors.append(f"{row['__location']}: duplicate utterance ID {key}")
        else:
            data_by_id[key] = row
        if isinstance(key[0], str) and isinstance(key[1], int):
            conversations[key[0]].append(key[1])
    for conversation_id, utterance_ids in sorted(conversations.items()):
        expected = list(range(1, len(utterance_ids) + 1))
        if sorted(utterance_ids) != expected:
            errors.append(f"{conversation_id}: utterance IDs are not consecutive from 1")

    review_rows = load_jsonl(args.review, errors)
    review_by_id: dict[tuple[str, int], dict[str, Any]] = {}
    for row in review_rows:
        validate_review_row(row, data_by_id, errors)
        key = (row.get("conversation_id"), row.get("utterance_id"))
        if key in review_by_id:
            errors.append(f"{row['__location']}: duplicate review ID {key}")
        review_by_id[key] = row

    required_review = {
        key for key, row in data_by_id.items() if row.get("is_phishing") and not row.get("labels")
    }
    missing_review = sorted(required_review - set(review_by_id))
    if missing_review:
        errors.append(f"true+empty utterances missing from review queue: {missing_review}")

    compare_staging(data_rows, args.staging, errors)

    label_counts = Counter(label for row in data_rows for label in row.get("labels", []))
    token_counts = Counter(
        token for row in data_rows for token in TOKEN_PATTERN.findall(row.get("text", ""))
    )
    true_count = sum(row.get("is_phishing") is True for row in data_rows)
    false_count = sum(row.get("is_phishing") is False for row in data_rows)
    false_with_labels = sum(
        row.get("is_phishing") is False and bool(row.get("labels")) for row in data_rows
    )

    for error in errors:
        print(f"ERROR: {error}")
    print("=== Masked Dataset Validation ===")
    print(f"Conversations: {len(conversations)}")
    print(f"Utterances: {len(data_rows)}")
    print(f"is_phishing true: {true_count}")
    print(f"is_phishing false: {false_count}")
    print(f"Duplicate utterance IDs: {duplicate_ids}")
    print(f"false with labels: {false_with_labels}")
    print(f"true with labels=[]: {len(required_review)}")
    print(f"Review queue: {len(review_rows)}")
    print("Labels: " + ", ".join(f"{label}={label_counts[label]}" for label in sorted(ALLOWED_LABELS)))
    print("Masking tokens: " + ", ".join(f"{token}={token_counts[token]}" for token in sorted(ALLOWED_TOKENS)))
    print(f"Errors: {len(errors)}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
