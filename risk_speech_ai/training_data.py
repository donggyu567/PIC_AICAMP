"""Join explicit labels with tuned text and prepare model-independent samples.

Missing label_status never implies that a row has been reviewed. Inputs may be
task-3 utterance dictionaries or other mappings containing the required keys.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from .config import MAX_HISTORY_UTTERANCES
from .labels import to_multi_hot

LABEL_STATUSES = ("reviewed", "out_of_taxonomy", "unreviewed")
_STRING_ID = re.compile(r"U(\d+)")


@dataclass(frozen=True)
class TrainingSample:
    conversation_id: str
    utterance_id: int | str
    history_texts: list[str]
    current_text: str
    risk_target: float
    type_targets: list[int]


@dataclass(frozen=True)
class BuildResult:
    samples: list[TrainingSample]
    statistics: dict[str, int]


def _key(row: Mapping[str, Any]) -> tuple[str, int | str]:
    conversation_id = row.get("conversation_id")
    utterance_id = row.get("utterance_id")
    if not isinstance(conversation_id, str) or not conversation_id.strip():
        raise ValueError("conversation_id must be a non-empty string")
    _order(utterance_id)
    return conversation_id, utterance_id


def _order(utterance_id: object) -> int:
    if isinstance(utterance_id, int) and not isinstance(utterance_id, bool) and utterance_id > 0:
        return utterance_id
    if isinstance(utterance_id, str):
        match = _STRING_ID.fullmatch(utterance_id)
        if match and int(match.group(1)) > 0:
            return int(match.group(1))
    raise ValueError("utterance_id must be a positive integer or U-prefixed positive number")


def _index(
    rows: Iterable[Mapping[str, Any]], statistics: Counter[str]
) -> dict[tuple[str, int | str], Mapping[str, Any]]:
    indexed: dict[tuple[str, int | str], Mapping[str, Any]] = {}
    ambiguous: set[tuple[str, int | str]] = set()
    order_ids: dict[tuple[str, int], int | str] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("each input row must be a mapping")
        key = _key(row)
        order_key = key[0], _order(key[1])
        if order_key in order_ids and order_ids[order_key] != key[1]:
            raise ValueError(
                f"ambiguous utterance order in {key[0]!r}: "
                f"{order_ids[order_key]!r} and {key[1]!r}"
            )
        order_ids[order_key] = key[1]
        if key in indexed or key in ambiguous:
            statistics["duplicate_key"] += 1
            indexed.pop(key, None)
            ambiguous.add(key)
        else:
            indexed[key] = row
    return indexed


def _targets(row: Mapping[str, Any]) -> tuple[float, list[int]]:
    status = row.get("label_status")
    if status not in LABEL_STATUSES:
        raise ValueError(f"invalid label_status: {status!r}")
    phishing = row.get("is_phishing")
    if not isinstance(phishing, bool):
        raise ValueError("is_phishing must be a boolean")
    labels = row.get("labels")
    if not isinstance(labels, list):
        raise ValueError("labels must be a list")
    types = to_multi_hot(labels)
    if status == "out_of_taxonomy":
        if not phishing or any(types):
            raise ValueError("out_of_taxonomy requires is_phishing=true and labels=[]")
    elif status == "reviewed":
        if phishing and not any(types):
            raise ValueError("reviewed phishing requires at least one type label")
        if not phishing and any(types):
            raise ValueError("reviewed normal requires labels=[]")
    return float(phishing), types


def build_training_samples(
    label_rows: Iterable[Mapping[str, Any]],
    tuned_rows: Iterable[Mapping[str, Any]],
) -> BuildResult:
    """Join by composite key, omit unresolved rows, and report every exclusion.

    All valid tuned utterances can supply history, including utterances without
    reviewed labels. Only the current utterance supplies a training target.
    Duplicate keys are excluded from their source index and cannot join.
    Conflicting ID spellings for one chronological position fail explicitly.
    Invalid tuned text is reported even when the utterance has no label.
    """

    statistics: Counter[str] = Counter()
    labels = _index(label_rows, statistics)
    tuned = _index(tuned_rows, statistics)
    label_keys, tuned_keys = set(labels), set(tuned)
    statistics["missing_tuned_text"] = len(label_keys - tuned_keys)
    statistics["missing_label"] = len(tuned_keys - label_keys)
    matched = label_keys & tuned_keys
    statistics["matched"] = len(matched)

    histories: dict[str, list[tuple[int, int | str, str]]] = defaultdict(list)
    valid_texts: dict[tuple[str, int | str], str] = {}
    for (conversation_id, utterance_id), row in tuned.items():
        value = row.get("tuned_text")
        if not isinstance(value, str):
            statistics["missing_tuned_text"] += 1
        elif not value.strip():
            statistics["empty_tuned_text"] += 1
        else:
            valid_texts[conversation_id, utterance_id] = value
            histories[conversation_id].append((_order(utterance_id), utterance_id, value))
    for entries in histories.values():
        entries.sort(key=lambda entry: entry[0])

    samples: list[TrainingSample] = []
    for key in sorted(matched, key=lambda item: (item[0], _order(item[1]), str(item[1]))):
        label_row = labels[key]
        if key not in valid_texts:
            continue
        value = valid_texts[key]
        status = label_row.get("label_status")
        if status is None:
            statistics["excluded_missing_status"] += 1
            continue
        if status == "unreviewed":
            statistics["excluded_unreviewed"] += 1
            continue
        if status not in LABEL_STATUSES:
            statistics["invalid_label"] += 1
            continue
        try:
            risk_target, type_targets = _targets(label_row)
        except ValueError:
            statistics["invalid_label"] += 1
            continue
        conversation_id, utterance_id = key
        previous = [
            text
            for order, _, text in histories[conversation_id]
            if order < _order(utterance_id)
        ]
        samples.append(
            TrainingSample(
                conversation_id=conversation_id,
                utterance_id=utterance_id,
                history_texts=previous[-MAX_HISTORY_UTTERANCES:],
                current_text=value,
                risk_target=risk_target,
                type_targets=type_targets,
            )
        )

    statistics["included"] = len(samples)
    for name in (
        "matched", "missing_tuned_text", "missing_label", "duplicate_key",
        "excluded_missing_status", "excluded_unreviewed", "invalid_label",
        "empty_tuned_text", "included",
    ):
        statistics.setdefault(name, 0)
    return BuildResult(samples=samples, statistics=dict(statistics))
