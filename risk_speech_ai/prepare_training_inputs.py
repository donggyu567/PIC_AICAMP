"""Build training JSONL from recorded approval evidence or team training-use policy."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

from .labels import LABELS
from .train_cli import read_jsonl

APPROVAL_SCOPE = "utterance_text_risk_and_eight_labels"
TEAM_POLICY = "team_lead_training_use_20261026_27"
TEAM_APPROVAL_SCOPE = "management_sheet_labeled_data_for_model_training"
BACKEND_MASK_TOKENS = {
    "[PERSON]", "[PHONE_NUMBER]", "[ACCOUNT_NUMBER]", "[RRN]", "[OTP]", "[ADDRESS]",
}
TOKEN_PATTERN = re.compile(r"\[[^\[\]\r\n]+\]")
DEFAULT_MANIFEST = Path(__file__).with_name("data_review_manifest_20261027.json")
RESTRICTED_CONVERSATIONS = {f"N{i:04d}" for i in range(15, 20)}
PHONE_PATTERN = re.compile(r"(?<!\d)01[016789][ -]?\d{3,4}[ -]?\d{4}(?!\d)")
EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
RRN_PATTERN = re.compile(r"(?<!\d)\d{6}[ -]?\d{7}(?!\d)")


def row_hash(row: dict[str, Any]) -> str:
    fields = {key: row.get(key) for key in
              ("conversation_id", "utterance_id", "text", "masked_text", "is_phishing", "labels")}
    encoded = json.dumps(fields, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _index(rows: list[dict[str, Any]]) -> dict[tuple[str, int], dict[str, Any]]:
    indexed = {}
    for row in rows:
        key = row.get("conversation_id"), row.get("utterance_id")
        if key in indexed:
            raise ValueError(f"duplicate evidence key: {key}")
        indexed[key] = row
    return indexed


def _source_rows(commit: str, path: str, conversation_id: str) -> list[dict[str, Any]]:
    if not path.startswith("dataset/") or not path.endswith(".jsonl"):
        raise ValueError(f"unexpected source path: {path}")
    result = subprocess.run(["git", "show", f"{commit}:{path}"], capture_output=True)
    if result.returncode:
        raise FileNotFoundError(f"source unavailable at {commit}: {path}")
    rows = [json.loads(line) for line in result.stdout.decode("utf-8-sig").splitlines() if line.strip()]
    return [row for row in rows if row.get("conversation_id") == conversation_id]


def _decision(row: dict[str, Any], approval: dict[str, Any] | None,
              correction: dict[str, Any] | None, commit: str) -> str | None:
    if approval is None:
        return "utterance_approval_missing"
    if (approval.get("scope") != APPROVAL_SCOPE or approval.get("data_commit") != commit
            or not isinstance(approval.get("reviewer"), str) or not approval["reviewer"].strip()
            or not isinstance(approval.get("evidence_url"), str) or not approval["evidence_url"].strip()
            or approval.get("row_sha256") != row_hash(row)
            or approval.get("masking_verified") is not True
            or approval.get("license_confirmed") is not True):
        return "approval_scope_or_version_unverified"
    status = approval.get("label_status")
    labels = row.get("labels")
    risk = row.get("is_phishing")
    if not isinstance(risk, bool) or not isinstance(labels, list) or any(label not in LABELS for label in labels):
        return "invalid_labels"
    if risk and not labels:
        if status != "out_of_taxonomy":
            return "risk_type_unresolved"
    elif status != "reviewed" or (not risk and labels):
        return "invalid_approval_status_or_labels"
    if correction is None:
        return "backend_correction_missing"
    masked = row.get("masked_text") if isinstance(row.get("masked_text"), str) else row.get("text")
    if not isinstance(masked, str) or not masked.strip():
        return "masked_text_missing"
    if (correction.get("schema_version") != "1.0"
            or correction.get("masked_text") != masked
            or correction.get("source_row_sha256") != row_hash(row)
            or correction.get("validation_status") != "passed"
            or not isinstance(correction.get("validation_source"), str)
            or not correction["validation_source"].strip()
            or not isinstance(correction.get("tuned_text"), str)
            or not correction["tuned_text"].strip()):
        return "backend_correction_unverified"
    unclear = correction.get("unclear_segments")
    if (type(correction.get("is_tuned")) is not bool
            or correction["is_tuned"] != (correction["tuned_text"] != masked)
            or type(correction.get("has_unclear")) is not bool
            or not isinstance(unclear, list)
            or any(not isinstance(item, str) or not item.strip() for item in unclear)
            or correction["has_unclear"] != bool(unclear)
            or correction["tuned_text"].count("[불명확]") != len(unclear)):
        return "backend_correction_unverified"
    source_tokens = TOKEN_PATTERN.findall(masked)
    tuned_tokens = TOKEN_PATTERN.findall(correction["tuned_text"])
    if (any(token not in BACKEND_MASK_TOKENS for token in source_tokens)
            or [token for token in tuned_tokens if token != "[불명확]"] != source_tokens):
        return "backend_mask_contract_mismatch"
    return None


def prepare(
    manifest: list[dict[str, Any]], approvals: list[dict[str, Any]],
    corrections: list[dict[str, Any]], commit: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    approval_by_key = _index(approvals)
    correction_by_key = _index(corrections)
    labels_out, tuned_out, pending = [], [], []
    seen = set()
    for entry in manifest:
        conversation_id = entry["id"]
        try:
            rows = _source_rows(commit, entry["path"], conversation_id)
        except FileNotFoundError:
            reason = ("human_review_license_and_source_pending"
                      if conversation_id in {f"N{i:04d}" for i in range(15, 20)}
                      else "source_file_missing")
            pending.append({"conversation_id": conversation_id, "reason": reason,
                            "source": entry["source"], "review": entry["review"]})
            continue
        if len(rows) != entry["expected_utterances"]:
            pending.append({"conversation_id": conversation_id, "reason": "source_count_mismatch",
                            "source": entry["source"], "review": entry["review"]})
            continue
        for row in rows:
            key = conversation_id, row.get("utterance_id")
            if key in seen:
                raise ValueError(f"duplicate source utterance key: {key}")
            seen.add(key)
            reason = None
            if entry["review"] != "통과":
                reason = "conversation_review_pending"
            elif (conversation_id in {f"N{i:04d}" for i in range(15, 20)}
                  and not (approval_by_key.get(key, {}).get("human_review_confirmed") is True
                           and approval_by_key.get(key, {}).get("derivative_use_permission") is True)):
                reason = "human_review_and_license_pending"
            elif (conversation_id.startswith("P") and 50 <= int(conversation_id[1:]) <= 59
                  and approval_by_key.get(key, {}).get("team_final_approved") is not True):
                reason = "team_final_review_pending"
            if reason is None:
                reason = _decision(row, approval_by_key.get(key), correction_by_key.get(key), commit)
            if reason:
                pending.append({"conversation_id": conversation_id, "utterance_id": key[1],
                                "reason": reason, "source": entry["source"],
                                "review": entry["review"]})
                continue
            approval = approval_by_key[key]
            correction = correction_by_key[key]
            labels_out.append({"conversation_id": conversation_id, "utterance_id": key[1],
                               "label_status": approval["label_status"],
                               "is_phishing": row["is_phishing"], "labels": row["labels"],
                               "approval_reviewer": approval["reviewer"],
                               "approval_evidence_url": approval["evidence_url"],
                               "approval_scope": approval["scope"],
                               "data_commit": commit, "source_row_sha256": row_hash(row)})
            tuned_out.append({"conversation_id": conversation_id, "utterance_id": key[1],
                              "tuned_text": correction["tuned_text"],
                              "validation_source": correction["validation_source"],
                              "source_row_sha256": row_hash(row)})
    return labels_out, tuned_out, pending


def prepare_team_approved(
    manifest: list[dict[str, Any]], commit: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Apply the user-reported team lead training-use approval without claiming human review."""
    labels_out, tuned_out, pending = [], [], []
    seen: set[tuple[str, int]] = set()
    for entry in manifest:
        conversation_id = entry["id"]
        expected = entry["expected_utterances"]
        if conversation_id in RESTRICTED_CONVERSATIONS:
            pending.extend({"conversation_id": conversation_id, "utterance_id": None,
                            "reason": "derivative_use_permission_unconfirmed", "source": entry["source"],
                            "excluded_utterance_count": expected} for _ in range(1))
            continue
        if not re.fullmatch(r"[PN]\d{4}", conversation_id) or not isinstance(entry.get("source"), str) or not entry["source"].strip():
            raise ValueError(f"invalid manifest identity or source: {conversation_id}")
        try:
            rows = _source_rows(commit, entry["path"], conversation_id)
        except FileNotFoundError:
            pending.append({"conversation_id": conversation_id, "utterance_id": None,
                            "reason": "source_file_missing", "source": entry["source"],
                            "excluded_utterance_count": expected})
            continue
        if len(rows) != expected:
            pending.append({"conversation_id": conversation_id, "utterance_id": None,
                            "reason": "source_count_mismatch", "source": entry["source"],
                            "excluded_utterance_count": expected, "actual_utterance_count": len(rows)})
            continue
        for row in rows:
            utterance_id = row.get("utterance_id")
            key = conversation_id, utterance_id
            if key in seen:
                raise ValueError(f"duplicate source utterance key: {key}")
            seen.add(key)
            reason = None
            labels = row.get("labels")
            risk = row.get("is_phishing")
            if not isinstance(utterance_id, int) or isinstance(utterance_id, bool) or utterance_id <= 0:
                reason = "invalid_utterance_id"
            elif "dataset/03. masked/" not in entry["path"]:
                reason = "masking_stage_unverified"
            elif not isinstance(risk, bool) or not isinstance(labels, list) or len(labels) != len(set(map(str, labels))) or any(not isinstance(label, str) or label not in LABELS for label in labels) or (not risk and labels):
                reason = "invalid_labels"
            elif risk and not labels:
                reason = "risk_type_unresolved"
            masked = row.get("masked_text") if isinstance(row.get("masked_text"), str) else row.get("text")
            text_source = "masked_text" if isinstance(row.get("masked_text"), str) else "text"
            if reason is None:
                if not isinstance(masked, str) or not masked.strip() or "\ufffd" in masked:
                    reason = "masked_text_missing_or_corrupt"
                elif any(token not in BACKEND_MASK_TOKENS for token in TOKEN_PATTERN.findall(masked)):
                    reason = "unknown_or_unsupported_mask_token"
                elif PHONE_PATTERN.search(masked) or EMAIL_PATTERN.search(masked) or RRN_PATTERN.search(masked):
                    reason = "unmasked_personal_identifier"
            if reason:
                pending.append({"conversation_id": conversation_id, "utterance_id": utterance_id,
                                "reason": reason, "source": entry["source"],
                                "excluded_utterance_count": 1})
                continue
            source_hash = row_hash(row)
            labels_out.append({"conversation_id": conversation_id, "utterance_id": utterance_id,
                               "label_status": "approved_for_training", "human_review_status": entry["review"],
                               "is_phishing": risk, "labels": labels,
                               "approval_policy": TEAM_POLICY, "approval_scope": TEAM_APPROVAL_SCOPE,
                               "data_commit": commit, "source_path": entry["path"],
                               "source": entry["source"], "source_item": entry.get("source_item"),
                               "source_row_sha256": source_hash})
            tuned_out.append({"conversation_id": conversation_id, "utterance_id": utterance_id,
                              "tuned_text": masked, "training_text_source": text_source,
                              "preprocessing": "masked_source_text_no_llm_correction",
                              "source_row_sha256": source_hash})
    return labels_out, tuned_out, pending


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def _file_sha256(path: Path | None) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path is not None else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-commit", required=True)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--approvals-jsonl", type=Path)
    parser.add_argument("--corrections-jsonl", type=Path)
    parser.add_argument("--approval-policy", choices=("utterance_evidence", TEAM_POLICY),
                        default="utterance_evidence")
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/risk_speech_ai/prepared"))
    args = parser.parse_args(argv)
    if not re.fullmatch(r"[0-9a-f]{40}", args.data_commit):
        parser.error("--data-commit must be a full 40-character Git commit hash")
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    approvals = read_jsonl(args.approvals_jsonl) if args.approvals_jsonl else []
    corrections = read_jsonl(args.corrections_jsonl) if args.corrections_jsonl else []
    if args.approval_policy == TEAM_POLICY:
        if args.approvals_jsonl or args.corrections_jsonl:
            parser.error("team training-use policy does not accept utterance evidence inputs")
        labels, tuned, pending = prepare_team_approved(manifest, args.data_commit)
    else:
        labels, tuned, pending = prepare(manifest, approvals, corrections, args.data_commit)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(args.output_dir / "labels.jsonl", labels)
    _write_jsonl(args.output_dir / "tuned.jsonl", tuned)
    _write_jsonl(args.output_dir / "pending.jsonl", pending)
    (args.output_dir / "provenance.json").write_text(json.dumps({
        "data_commit": args.data_commit,
        "data_version": f"risk-speech-{args.approval_policy}-{args.data_commit[:12]}",
        "manifest": str(args.manifest),
        "manifest_sha256": _file_sha256(args.manifest),
        "approvals_sha256": _file_sha256(args.approvals_jsonl),
        "corrections_sha256": _file_sha256(args.corrections_jsonl),
        "review_sheet": "https://docs.google.com/spreadsheets/d/1a5EJQRg6Hvw-i6WJnFi4LuT8E_BDPxdBfFg5ADEj954/edit",
        "approval_scope": TEAM_APPROVAL_SCOPE if args.approval_policy == TEAM_POLICY else APPROVAL_SCOPE,
        "approval_policy": args.approval_policy,
        "approval_basis": "User-reported team-lead decision on 2026-10-26/27 to use management-sheet labeled data for model training" if args.approval_policy == TEAM_POLICY else "per-utterance evidence",
        "human_review_claimed": False if args.approval_policy == TEAM_POLICY else None,
        "preprocessing": "masked_source_text_no_llm_correction" if args.approval_policy == TEAM_POLICY else "validated_backend_correction",
        "approved_utterances": len(labels),
        "pending_reasons": dict(Counter({reason: sum(row.get("excluded_utterance_count", 1)
                                                 for row in pending if row["reason"] == reason)
                                         for reason in {row["reason"] for row in pending}})),
        "excluded_utterances": sum(row.get("excluded_utterance_count", 1) for row in pending),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"approved={len(labels)} pending={len(pending)} output={args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
