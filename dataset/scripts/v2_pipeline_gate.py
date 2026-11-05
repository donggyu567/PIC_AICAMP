"""Separate read-only preflight samples from policy-approved training inputs.

This module has no optimizer, training CLI, checkpoint writer or approval writer.
Training eligibility comes from the existing two-person CSV evidence and a
separate explicit training-use decision, never from generated labels alone.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass

from prepare_pilot_review import REVIEWERS
from restore_pilot import LABELS, UTTERANCE_FIELDS
from validate_masked import ALLOWED_TOKENS, VALID_SPEAKERS


class PipelineGateError(ValueError):
    pass


def fingerprint(conversations):
    return hashlib.sha256(json.dumps(conversations, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def validate_partition(conversations, split):
    if split not in {"train", "validation"} or not conversations:
        raise PipelineGateError("Explicit nonempty train/validation partition required")
    seen, families, scenarios = set(), set(), set()
    for c in conversations:
        cid = c["synthetic_id"]
        if c["split"] != split:
            raise PipelineGateError(f"Split mixture: expected {split}, got {c['split']} in {cid}")
        if (cid in seen or c["scenario_family_id"] in families or c["scenario_id"] in scenarios
                or c["is_synthetic"] is not True or c["actual_call"] is not False):
            raise PipelineGateError(f"Identity/synthetic provenance invalid: {cid}")
        seen.add(cid)
        families.add(c["scenario_family_id"])
        scenarios.add(c["scenario_id"])
        for position, u in enumerate(c["utterances"], 1):
            if (set(u) != UTTERANCE_FIELDS or type(u["utterance_id"]) is not int
                    or u["utterance_id"] != position or u["speaker"] not in VALID_SPEAKERS
                    or not isinstance(u["text"], str) or not u["text"].strip()
                    or not isinstance(u["label_rationale"], str) or not u["label_rationale"].strip()
                    or type(u["is_phishing"]) is not bool or not isinstance(u["labels"], list)
                    or any(label not in LABELS for label in u["labels"])
                    or len(u["labels"]) != len(set(u["labels"]))
                    or u["is_phishing"] != bool(u["labels"])):
                raise PipelineGateError(f"Utterance/label contract invalid: {cid}-{position}")
            if (set(re.findall(r"\[([^\]]+)\]", u["text"])) - ALLOWED_TOKENS
                    or re.search(r"(?:\d[ -]?){7,}|https?://|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", u["text"])):
                raise PipelineGateError(f"Masking contract invalid: {cid}-{position}")


def approval_audit(conversations, reviews, training_use_decision=None):
    """Audit existing evidence only; returns reasons without writing approvals."""
    validate_partition(conversations, "train")
    indexed = {}
    for row in reviews:
        key = row["발화_ID"]
        if key in indexed:
            raise PipelineGateError("Duplicate review evidence ID")
        indexed[key] = row
    reasons, rows = Counter(), []
    expected_ids = {f"{c['synthetic_id']}-{u['utterance_id']}" for c in conversations for u in c["utterances"]}
    if set(indexed) != expected_ids:
        raise PipelineGateError("Review coverage must equal this partition exactly")
    for c in conversations:
        for u in c["utterances"]:
            key = f"{c['synthetic_id']}-{u['utterance_id']}"
            row, pending = indexed[key], []
            if (row["대화_ID"] != c["synthetic_id"] or row["발화_번호"] != str(u["utterance_id"])
                    or row["화자"] != u["speaker"] or row["대화_요약"] != c["scenario_summary"]
                    or row["발화_내용"] != u["text"] or row["라벨_근거"] != u["label_rationale"]
                    or row["피싱_여부"] != str(u["is_phishing"]).lower()
                    or json.loads(row["위험_유형"]) != u["labels"]):
                raise PipelineGateError(f"Review evidence does not match source: {key}")
            for name in REVIEWERS:
                if row[f"검수_결과_{name}"] != "승인":
                    pending.append(f"review_not_approved:{name}")
                if not row[f"검수_일시_{name}"].strip():
                    pending.append(f"review_time_missing:{name}")
                if row[f"수정_의견_{name}"].strip():
                    pending.append(f"review_comment_unresolved:{name}")
            if row["최종_합의_결과"] != "승인" or not row["최종_합의_일시"].strip():
                pending.append("final_agreement_missing")
            if row["합의_수정안"].strip():
                pending.append("source_revision_not_applied_and_reviewed")
            reasons.update(pending)
            rows.append(dict(utterance_id=key, review_eligible=not pending, reasons=pending))
    decision = training_use_decision or {}
    authorization_valid = (decision.get("approved_for_training") is True
        and decision.get("dataset_fingerprint") == fingerprint(conversations)
        and all(isinstance(decision.get(k), str) and decision[k].strip() for k in ("authorized_by", "authorized_at", "evidence_reference")))
    if not authorization_valid:
        reasons["explicit_training_use_decision_missing_or_not_bound_to_dataset"] = len(rows)
    ready = all(r["review_eligible"] for r in rows) and authorization_valid
    return dict(status="READY" if ready else "BLOCKED", utterances=len(rows),
                fully_reviewed_utterances=sum(r["review_eligible"] for r in rows),
                eligible_for_normal_training=len(rows) if ready else 0,
                training_use_decision_verified=authorization_valid, reason_counts=dict(reasons), rows=rows)


@dataclass(frozen=True)
class PreparedPartition:
    split: str
    mode: str
    samples: list
    training_allowed: bool


def prepare_partition(conversations, *, split, mode, sample_type, to_multi_hot,
                      reviews=None, training_use_decision=None):
    if mode not in {"preflight", "training"}:
        raise PipelineGateError("Explicit preflight or training mode required")
    validate_partition(conversations, split)
    if mode == "training":
        if split != "train":
            raise PipelineGateError("VALIDATION can never enter the training route")
        result = approval_audit(conversations, reviews or [], training_use_decision)
        if result["status"] != "READY":
            raise PipelineGateError("Human review/final agreement/training-use evidence incomplete; entire dataset blocked")
    samples = []
    for c in conversations:
        for index, u in enumerate(c["utterances"]):
            history = [h["text"] for h in c["utterances"][max(0, index-5):index]]
            samples.append(sample_type(c["synthetic_id"], u["utterance_id"], history, u["text"],
                                       float(u["is_phishing"]), to_multi_hot(u["labels"])))
    return PreparedPartition(split, mode, samples, mode == "training")
