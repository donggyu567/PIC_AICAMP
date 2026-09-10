#!/usr/bin/env python3
"""Report duplicate candidates in raw dataset conversations."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Iterable


SIMILARITY_THRESHOLD = 0.90
VALID_CONVERSATION_STATUSES = {"reserved", "raw_added", "labeled", "validated"}


@dataclass(frozen=True)
class Utterance:
    conversation_id: str
    utterance_id: int
    text: str
    source: str


@dataclass(frozen=True)
class Conversation:
    conversation_id: str
    source: str
    transcript: str
    fingerprint: str


def normalize_text(text: str) -> str:
    """Normalize text only for duplicate comparison; source data is unchanged."""

    without_newlines = text.replace("\r", "").replace("\n", "")
    collapsed = re.sub(r"\s+", " ", without_newlines).strip().casefold()
    without_punctuation = "".join(
        character
        for character in collapsed
        if not unicodedata.category(character).startswith("P")
    )
    return re.sub(r"\s+", " ", without_punctuation).strip()


def load_raw_utterances(raw_dir: Path) -> tuple[list[Utterance], list[str]]:
    """Load JSON utterances under raw_dir without scanning derived outputs."""

    utterances: list[Utterance] = []
    errors: list[str] = []
    for path in sorted(raw_dir.rglob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            utterances.append(
                Utterance(
                    conversation_id=payload["conversation_id"],
                    utterance_id=payload["utterance_id"],
                    text=payload["text"],
                    source=payload["source"],
                )
            )
        except (KeyError, TypeError, UnicodeDecodeError, json.JSONDecodeError) as error:
            errors.append(f"{path}: cannot read duplicate-check fields ({error})")
    return utterances, errors


def group_duplicates(
    utterances: Iterable[Utterance], key: callable
) -> list[list[Utterance]]:
    grouped: dict[str, list[Utterance]] = defaultdict(list)
    for utterance in utterances:
        grouped[key(utterance)].append(utterance)
    return [group for group in grouped.values() if len(group) > 1]


def build_conversations(utterances: Iterable[Utterance]) -> list[Conversation]:
    grouped: dict[str, list[Utterance]] = defaultdict(list)
    for utterance in utterances:
        grouped[utterance.conversation_id].append(utterance)

    conversations: list[Conversation] = []
    for conversation_id, entries in sorted(grouped.items()):
        ordered = sorted(entries, key=lambda entry: entry.utterance_id)
        transcript = "\n".join(normalize_text(entry.text) for entry in ordered)
        conversations.append(
            Conversation(
                conversation_id=conversation_id,
                source=ordered[0].source,
                transcript=transcript,
                fingerprint=hashlib.sha256(transcript.encode("utf-8")).hexdigest(),
            )
        )
    return conversations


def duplicate_conversations(
    conversations: Iterable[Conversation],
) -> list[list[Conversation]]:
    grouped: dict[str, list[Conversation]] = defaultdict(list)
    for conversation in conversations:
        grouped[conversation.fingerprint].append(conversation)
    return [group for group in grouped.values() if len(group) > 1]


def similar_conversations(conversations: list[Conversation]) -> list[tuple[Conversation, Conversation, float]]:
    candidates: list[tuple[Conversation, Conversation, float]] = []
    for index, first in enumerate(conversations):
        for second in conversations[index + 1 :]:
            if first.fingerprint == second.fingerprint:
                continue
            similarity = SequenceMatcher(None, first.transcript, second.transcript).ratio()
            if similarity >= SIMILARITY_THRESHOLD:
                candidates.append((first, second, similarity))
    return candidates


def duplicate_registry_values(registry_path: Path) -> tuple[list[list[dict[str, str]]], list[list[dict[str, str]]]]:
    with registry_path.open(encoding="utf-8", newline="") as file:
        entries = list(csv.DictReader(file))

    def duplicates(field: str) -> list[list[dict[str, str]]]:
        grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
        for entry in entries:
            value = entry.get(field, "").strip()
            if value:
                grouped[value].append(entry)
        return [group for group in grouped.values() if len(group) > 1]

    return duplicates("source_url"), duplicates("source_name")


def validate_conversation_registry(
    conversation_registry_path: Path, source_registry_path: Path
) -> list[str]:
    """Validate reservation ownership without treating shared sources as duplicates."""

    with source_registry_path.open(encoding="utf-8", newline="") as file:
        sources = {
            row["source_id"]: row
            for row in csv.DictReader(file)
            if row.get("source_id")
        }
    with conversation_registry_path.open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))

    errors: list[str] = []
    seen_conversation_ids: set[str] = set()
    seen_source_items: set[tuple[str, str]] = set()
    for row_number, row in enumerate(rows, start=2):
        conversation_id = row.get("conversation_id", "").strip()
        source_id = row.get("source_id", "").strip()
        source_item_id = row.get("source_item_id", "").strip()
        data_type = row.get("data_type", "").strip()
        status = row.get("status", "").strip()

        if conversation_id:
            if conversation_id in seen_conversation_ids:
                errors.append(
                    f"conversation registry row {row_number}: duplicate conversation_id {conversation_id}"
                )
            seen_conversation_ids.add(conversation_id)
        if source_item_id:
            source_item_key = (source_id, source_item_id)
            if source_item_key in seen_source_items:
                errors.append(
                    "conversation registry row "
                    f"{row_number}: duplicate source_id/source_item_id {source_item_key}"
                )
            seen_source_items.add(source_item_key)
        if source_id not in sources:
            errors.append(
                f"conversation registry row {row_number}: unknown source_id {source_id}"
            )
        elif data_type != sources[source_id].get("data_type", "").strip():
            errors.append(
                "conversation registry row "
                f"{row_number}: data_type {data_type} does not match source {source_id}"
            )
        if status not in VALID_CONVERSATION_STATUSES:
            errors.append(
                f"conversation registry row {row_number}: invalid status {status}"
            )
    return errors


def run_check(
    raw_dir: Path,
    registry_path: Path,
    conversation_registry_path: Path | None = None,
) -> tuple[int, str]:
    utterances, errors = load_raw_utterances(raw_dir)
    exact_groups = group_duplicates(utterances, lambda utterance: utterance.text)
    normalized_groups = group_duplicates(
        utterances, lambda utterance: normalize_text(utterance.text)
    )
    normalized_only_groups = [
        group for group in normalized_groups if len({item.text for item in group}) > 1
    ]
    conversations = build_conversations(utterances)
    duplicate_conversation_groups = duplicate_conversations(conversations)
    similar_candidates = similar_conversations(conversations)
    url_groups, name_groups = duplicate_registry_values(registry_path)
    if conversation_registry_path is not None:
        errors.extend(
            validate_conversation_registry(conversation_registry_path, registry_path)
        )

    lines: list[str] = []
    for group in exact_groups:
        lines.extend(["[WARNING] Exact utterance duplicate"])
        lines.extend(f"- {item.conversation_id}:{item.utterance_id}" for item in group)
        lines.append(f"text: {group[0].text}")
    for group in normalized_only_groups:
        lines.extend(["[WARNING] Normalized utterance duplicate"])
        lines.extend(f"- {item.conversation_id}:{item.utterance_id}" for item in group)
        lines.append(f"normalized text: {normalize_text(group[0].text)}")
    for group in duplicate_conversation_groups:
        lines.extend(["[ERROR] Duplicate conversation detected"])
        lines.extend(item.conversation_id for item in group)
        lines.append("These conversations have identical normalized transcripts.")
    for first, second, similarity in similar_candidates:
        lines.extend(
            [
                "[WARNING] Similar conversation candidate",
                f"{first.conversation_id} <-> {second.conversation_id}",
                f"similarity: {similarity:.2f}",
            ]
        )
        if first.source == second.source:
            lines.append(f"same source: {first.source}")
    for group in url_groups:
        lines.append("[WARNING] Duplicate source URL: " + group[0]["source_url"])
        lines.extend(f"- {entry['source_id']}" for entry in group)
    for group in name_groups:
        lines.append("[WARNING] Duplicate source name: " + group[0]["source_name"])
        lines.extend(f"- {entry['source_id']}" for entry in group)

    warning_count = (
        len(exact_groups)
        + len(normalized_only_groups)
        + len(similar_candidates)
        + len(url_groups)
        + len(name_groups)
    )
    lines.extend(
        [
            "=== Dataset Duplicate Check ===",
            "",
            f"Conversations scanned: {len(conversations)}",
            f"Utterances scanned: {len(utterances)}",
            "",
            f"Exact utterance duplicate groups: {len(exact_groups)}",
            f"Normalized utterance duplicate groups: {len(normalized_groups)}",
            "",
            f"Exact duplicate conversations: {len(duplicate_conversation_groups)}",
            f"Similar conversation candidates: {len(similar_candidates)}",
            "",
            f"Duplicate source URLs: {len(url_groups)}",
            f"Duplicate source names: {len(name_groups)}",
            "",
            f"Errors: {len(errors) + len(duplicate_conversation_groups)}",
            f"Warnings: {warning_count}",
        ]
    )
    lines.extend(f"[ERROR] {error}" for error in errors)
    return (1 if errors or duplicate_conversation_groups else 0), "\n".join(lines)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(
        description="Check duplicate candidates in dataset/raw.",
        epilog=(
            "Before collection: verify source_registry, verify conversation_registry and "
            "source_item_id, reserve the conversation, then add raw data. Update status "
            "from reserved to raw_added, labeled, and validated as work completes."
        ),
    )
    parser.add_argument("raw_dir", nargs="?", type=Path, default=root / "raw")
    parser.add_argument("--registry", type=Path, default=root / "metadata" / "source_registry.csv")
    parser.add_argument(
        "--conversation-registry",
        type=Path,
        default=root / "metadata" / "conversation_registry.csv",
    )
    args = parser.parse_args()
    exit_code, output = run_check(
        args.raw_dir, args.registry, args.conversation_registry
    )
    print(output)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
