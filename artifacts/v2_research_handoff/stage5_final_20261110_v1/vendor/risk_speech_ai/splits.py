"""Plan future conversation-level splits while grouping shared source material."""

from __future__ import annotations

import random
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence


def plan_conversation_splits(
    label_rows: Sequence[Mapping], tuned_rows: Sequence[Mapping], *, data_version: str,
    ratios: tuple[float, float, float] = (0.8, 0.1, 0.1), seed: int = 42,
    group_by_source: bool = True,
) -> dict:
    """Return a proposed split plan; never label previously trained rows as independent TEST."""
    if not data_version or len(ratios) != 3 or any(not 0 < value < 1 for value in ratios) or abs(sum(ratios) - 1) > 1e-9:
        raise ValueError("data_version and positive train/validation/test ratios summing to 1 are required")
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise ValueError("seed must be an integer")
    conversations = {row["conversation_id"] for row in label_rows}
    if not conversations:
        raise ValueError("no conversations")
    parent = {conversation: conversation for conversation in conversations}

    def find(value: str) -> str:
        while parent[value] != value:
            parent[value] = parent[parent[value]]
            value = parent[value]
        return value

    def join(left: str, right: str) -> None:
        parent[find(left)] = find(right)

    seen_material: dict[tuple[str, str], str] = {}
    for row in label_rows:
        conversation = row["conversation_id"]
        for kind, value in (("source_item", row.get("source_item")),
                            ("source", row.get("source") if group_by_source else None)):
            if isinstance(value, str) and value.strip():
                key = kind, value.strip()
                if key in seen_material:
                    join(conversation, seen_material[key])
                else:
                    seen_material[key] = conversation
    for row in tuned_rows:
        conversation = row["conversation_id"]
        if conversation not in conversations:
            continue
        text = row.get("tuned_text")
        if isinstance(text, str) and text.strip():
            key = "identical_text", text.strip()
            if key in seen_material:
                join(conversation, seen_material[key])
            else:
                seen_material[key] = conversation

    groups: dict[str, set[str]] = defaultdict(set)
    for conversation in sorted(conversations):
        groups[find(conversation)].add(conversation)
    utterances = Counter(row["conversation_id"] for row in label_rows)
    components = list(groups.values())
    if len(components) < 3:
        raise ValueError("fewer than three independent source/text components")
    random.Random(seed).shuffle(components)
    components.sort(key=lambda component: -sum(utterances[conversation] for conversation in component))
    names = ("train", "validation", "test")
    targets = dict(zip(names, (value * len(label_rows) for value in ratios)))
    counts = Counter()
    assignment = {}
    for index, component in enumerate(components):
        split = names[index] if index < 3 else max(names, key=lambda name: targets[name] - counts[name])
        for conversation in component:
            assignment[conversation] = split
            counts[split] += utterances[conversation]
    assert len(assignment) == len(conversations)
    if any(counts[name] == 0 for name in names):
        raise ValueError("could not populate all three splits without leakage")
    return {"data_version": data_version, "seed": seed,
            "requested_ratios": dict(zip(names, ratios)),
            "group_by_source": group_by_source,
            "component_count": len(components),
            "conversation_to_split": assignment,
            "utterance_counts": {name: counts[name] for name in names},
            "warning": "Any row already used to train an existing checkpoint remains in-sample for that checkpoint."}
