#!/usr/bin/env python3
"""Prepare explicitly single-reviewed candidates against a pinned Git implementation.

No training, final approval, original edits, checkout, checkpoint writes or split
assignment occur here. The adapter requires explicit opt-in for candidate use.
"""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import importlib
import json
import re
import subprocess
import sys
import unicodedata
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path

import prepare_pilot_review as review
import restore_pilot as source

ROOT = review.ROOT
REVISION = "958c30e4ac6c43af015b1af75b295bfc1b6dfbcc"
REFERENCE = ROOT / "artifacts/v1_reference" / REVISION[:12]
OUTPUT = ROOT / "dataset/04. processed/v2_pilot/training_candidate"
REPORTS = ROOT / "reports/v2_pilot/training_readiness"
WORKING = ROOT / "dataset/review/v2_pilot/human_review_working.csv"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"".join((json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8") for row in rows))


def recover_reference():
    paths = git("ls-tree", "-r", "--name-only", REVISION, "--", "risk_speech_ai").decode().splitlines()
    paths += ["requirements-ai.txt", "tests/test_training_data.py", "tests/test_tokenization.py", "tests/test_dataset.py"]
    records = []
    for relative in paths:
        data = git("show", f"{REVISION}:{relative}")
        target = REFERENCE / relative
        if target.exists():
            source.require(target.read_bytes() == data, f"Recovered reference was modified: {relative}")
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        records.append({"path": relative, "sha256": sha(data),
                        "git_blob": hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()})
    manifest = {"revision": REVISION, "source_ref": "origin/codex/backend-ai-integration",
                "note": "Exact Git source snapshot; its use in an actual v1 training run is not established by the available artifacts.",
                "working_branch_unchanged": git("rev-parse", "HEAD").decode().strip(), "files": records}
    write_json(REFERENCE / "source_manifest.json", manifest)
    return manifest


def load_reference():
    sys.path.insert(0, str(REFERENCE))
    module = importlib.import_module("risk_speech_ai.training_data")
    source.require(Path(module.__file__).resolve().is_relative_to(REFERENCE.resolve()), "Unexpected training module loaded")
    labels = importlib.import_module("risk_speech_ai.labels")
    source.require(tuple(labels.LABELS) == source.LABELS, "Label order differs from source pilot")
    return module, labels


def load_reviewed_candidates():
    baseline = {row["발화_ID"]: row for row in review.expected_rows()}
    with WORKING.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        source.require(reader.fieldnames == review.COLUMNS, "Review CSV columns differ")
        rows = list(reader)
    source.require(len(rows) == 136 and len({row["발화_ID"] for row in rows}) == 136, "Expected 136 unique review rows")
    source.require({row["발화_ID"] for row in rows} == set(baseline), "Review coverage differs")
    indexed = {row["발화_ID"]: row for row in rows}
    for row in rows:
        source.require(all(row[key] == baseline[row["발화_ID"]][key] for key in review.SOURCE_COLUMNS), "Source CSV cells changed")
        source.require(row["검수_결과_임정윤"] == "승인", f"Single review missing: {row['발화_ID']}")
        source.require(not row["수정_의견_임정윤"].strip(), f"Unresolved single-review comment: {row['발화_ID']}")
    canonical = [source.parse_json(line) for line in review.CANONICAL.read_text(encoding="utf-8").splitlines()]
    expected, _ = source.restore()
    source.validate(canonical, expected)
    review_sha = sha(WORKING.read_bytes())
    matching_entries = []
    for path in sorted((ROOT / "reports/v2_pilot/review_entries").glob("*.json")):
        entry = json.loads(path.read_text(encoding="utf-8"))
        if entry.get("working_csv_sha256_after") == review_sha and entry.get("reviewer") == "임정윤":
            matching_entries.append({"file": path.relative_to(ROOT).as_posix(), "recorded_at": entry["recorded_at"],
                                     "original_human_reviewed_at": entry.get("original_human_reviewed_at")})
    candidates = []
    for original in canonical:
        candidate = copy.deepcopy(original)
        candidate["review_preparation"] = {
            "stage": "single_review_train_candidate", "completed_reviewers": ["임정윤"],
            "final_approved": False, "review_csv_sha256": review_sha,
            "canonical_sha256": sha(review.CANONICAL.read_bytes()),
            "approval_entry_provenance": matching_entries,
            "reviewer_results": [{"utterance_id": u["utterance_id"],
                                  "임정윤": indexed[f"{original['synthetic_id']}-{u['utterance_id']}"]["검수_결과_임정윤"],
                                  "김해린": indexed[f"{original['synthetic_id']}-{u['utterance_id']}"]["검수_결과_김해린"],
                                  "final_agreement": indexed[f"{original['synthetic_id']}-{u['utterance_id']}"]["최종_합의_결과"]}
                                 for u in original["utterances"]],
            "policy_note": "Single-review candidate only. Existing two-person final approval policy remains unchanged. Original review times are not inferred from entry times.",
        }
        source.require({key: value for key, value in candidate.items() if key != "review_preparation"} == original, "Original conversation changed")
        candidates.append(candidate)
    return candidates, rows


def convert_candidates(conversations, *, allow_single_review_candidate=False):
    source.require(allow_single_review_candidate, "Explicit single-review candidate opt-in is required")
    labels, tuned, metadata = [], [], []
    seen, families = set(), set()
    for c in conversations:
        cid = c["synthetic_id"]
        source.require(cid not in seen, "Duplicate conversation ID")
        source.require(c["scenario_family_id"] not in families, "Duplicate scenario family")
        seen.add(cid)
        families.add(c["scenario_family_id"])
        source.require(c["split"] == "train" and c["is_synthetic"] is True and c["actual_call"] is False, "Only synthetic TRAIN candidates are accepted")
        stage = c["review_preparation"]
        source.require(stage["stage"] == "single_review_train_candidate" and stage["final_approved"] is False, "Candidate/final approval state mismatch")
        statuses = {u["utterance_id"]: u for u in stage["reviewer_results"]}
        for position, u in enumerate(c["utterances"], 1):
            source.require(type(u["utterance_id"]) is int and u["utterance_id"] == position, "Nonconsecutive utterances")
            source.require(statuses.get(position, {}).get("임정윤") == "승인", "Unreviewed target/history must never enter converter")
            provenance = {"split": "train", "is_synthetic": True, "source_kind": c["source_kind"],
                          "actual_call": False, "scenario_family_id": c["scenario_family_id"],
                          "approval_stage": stage["stage"], "final_approved": False}
            common = {"conversation_id": cid, "utterance_id": position, **provenance}
            labels.append({**common, "label_status": "reviewed", "is_phishing": u["is_phishing"], "labels": copy.deepcopy(u["labels"]),
                           "review_status_note": "Internal v1 loader reviewed label maps to one explicit reviewer; it is not two-person final approval."})
            tuned.append({**common, "tuned_text": u["text"], "text_transform": "identity_from_canonical; no LLM correction or added raw text"})
        metadata.append({"conversation_id": cid, **{k: v for k, v in c.items() if k != "utterances"}})
    return labels, tuned, metadata


def normalize(text):
    return "".join(c for c in unicodedata.normalize("NFKC", text).casefold()
                   if not c.isspace() and not unicodedata.category(c).startswith("P"))


def duplicate_audit(candidates, actual_splits):
    pilot = [(c["synthetic_id"], u["utterance_id"], u["text"]) for c in candidates for u in c["utterances"]]
    reference = source.duplicate_report(candidates)
    unique = {}
    for info in reference["local_files_scanned"]:
        path = ROOT / info["file"]
        text = path.read_text(encoding="utf-8-sig")
        entries = [source.parse_json(text)] if path.suffix == ".json" else [source.parse_json(line) for line in text.splitlines() if line.strip()]
        for entry in entries:
            if all(k in entry for k in ("conversation_id", "utterance_id", "text")):
                key = (entry["conversation_id"], entry["utterance_id"], entry["text"])
                unique.setdefault(key, info["file"])
    near = []
    for cid, uid, text in pilot:
        a = normalize(text)
        for (other_cid, other_uid, other_text), path in unique.items():
            b = normalize(other_text)
            if a == b:
                continue
            matcher = SequenceMatcher(None, a, b, autojunk=False)
            if matcher.real_quick_ratio() >= .90 and matcher.quick_ratio() >= .90:
                ratio = matcher.ratio()
                if ratio >= .90:
                    near.append({"pilot": f"{cid}-{uid}", "reference": f"{other_cid}:{other_uid}",
                                 "similarity": round(ratio, 6), "reference_file": path})
    reference["near_utterance_candidates"] = near
    reference["scope"] = "Local reference data only; this is NOT the actual v1 training-input duplicate check."
    reference["scenario_limitation"] = "Full transcript sequence similarity is screened. No semantic model or actual v1 scenario descriptions were available; semantic scenario equivalence is unverified."
    # Optional actual split inputs must be supplied explicitly; never infer a
    # training split from a reference directory name.
    indexed = []
    files = []
    for split, paths in actual_splits.items():
        for path in paths:
            rows = [source.parse_json(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
            files.append({"split": split, "path": str(path), "sha256": sha(path.read_bytes()), "rows": len(rows)})
            for row in rows:
                embedded = row.get("split", split)
                source.require(embedded == split, f"Split metadata disagrees: {path}")
                nested = row.get("utterances", [row])
                for u in nested:
                    text = u.get("text", u.get("current_text", u.get("tuned_text")))
                    source.require(isinstance(text, str) and text.strip(), f"Unsupported actual input text schema: {path}")
                    indexed.append({"split": split, "text": text, "key": (row.get("conversation_id", row.get("synthetic_id")), u.get("utterance_id")),
                                    "family": row.get("scenario_family_id")})
    pilot_matches, split_leaks, family_leaks = [], [], []
    for cid, uid, text in pilot:
        a = normalize(text)
        for other in indexed:
            b = normalize(other["text"])
            matcher = SequenceMatcher(None, a, b, autojunk=False)
            if a == b or (matcher.real_quick_ratio() >= .90 and matcher.quick_ratio() >= .90 and matcher.ratio() >= .90):
                pilot_matches.append({"pilot": f"{cid}-{uid}", "actual_v1": other["key"], "split": other["split"],
                                      "kind": "exact" if text == other["text"] else "normalized" if a == b else "similar"})
    texts = defaultdict(set)
    families = defaultdict(set)
    for row in indexed:
        texts[normalize(row["text"])].add(row["split"])
        if row["family"]:
            families[row["family"]].add(row["split"])
    split_leaks = [{"normalized_text_sha256": sha(text.encode()), "splits": sorted(splits)} for text, splits in texts.items() if len(splits) > 1]
    for c in candidates:
        families[c["scenario_family_id"]].add("train")
    family_leaks = [{"family": name, "splits": sorted(splits)} for name, splits in families.items() if len(splits) > 1]
    return reference, {"status": "NOT_VERIFIED_ACTUAL_INPUTS_MISSING" if not files else "CHECKED_SUPPLIED_FILES_ONLY",
                       "actual_files": files, "pilot_matches": pilot_matches, "cross_split_exact_normalized": split_leaks,
                       "cross_split_families": family_leaks,
                       "all_three_splits_supplied": all(actual_splits.get(name) for name in ("train", "validation", "test")),
                       "required_paths": ["Actual v1 train label/tuned-text input JSONL or its exported sample JSONL", "Actual v1 validation/test sample JSONL and split manifest", "Actual trained v1 checkpoint path and run metadata"],
                       "note": "No records were deleted or assigned to validation/test. Absence of actual inputs is not a passing duplicate result."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-single-review-candidate", action="store_true")
    for split in ("train", "validation", "test"):
        parser.add_argument(f"--v1-{split}", type=Path, action="append", default=[])
    args = parser.parse_args()
    source.require(args.allow_single_review_candidate, "Explicit single-review candidate opt-in is required")
    protected = [review.CANONICAL, WORKING, review.CSV_PATH, WORKING.with_name("WORKING_REVIEW_GUIDE.md")]
    protected += sorted((ROOT / "dataset/04. processed/v2_pilot").glob("approval_*/*.jsonl"))
    before = {str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in protected}
    manifest = recover_reference()
    module, labels = load_reference()
    candidates, reviews = load_reviewed_candidates()
    label_rows, tuned_rows, metadata = convert_candidates(candidates, allow_single_review_candidate=True)
    built = module.build_training_samples(label_rows, tuned_rows)
    source.require(len(built.samples) == 136 and built.statistics["invalid_label"] == 0, "Actual v1 sample builder excluded pilot rows")
    history_audit = []
    for c in candidates:
        samples = [s for s in built.samples if s.conversation_id == c["synthetic_id"]]
        for i, sample in enumerate(samples):
            expected = [u["text"] for u in c["utterances"][max(0, i - 5):i]]
            source.require(sample.history_texts == expected and sample.current_text == c["utterances"][i]["text"], "History/order/current changed")
            source.require(sample.type_targets == labels.to_multi_hot(c["utterances"][i]["labels"]), "Multi-label target changed")
            history_audit.append({"conversation_id": sample.conversation_id, "utterance_id": sample.utterance_id,
                                  "history_utterance_ids": list(range(max(1, sample.utterance_id - 5), sample.utterance_id))})
    write_jsonl(OUTPUT / "pilot_single_review_train_candidate.jsonl", candidates)
    write_jsonl(OUTPUT / "v1_adapter_label_candidates.jsonl", label_rows)
    write_jsonl(OUTPUT / "v1_adapter_text_candidates.jsonl", tuned_rows)
    write_jsonl(OUTPUT / "conversation_provenance.jsonl", metadata)
    from dataclasses import asdict
    write_jsonl(OUTPUT / "v1_adapter_sample_candidates.jsonl", [{**asdict(s), "split": "train", "is_synthetic": True,
                  "approval_stage": "single_review_train_candidate", "final_approved": False} for s in built.samples])
    reference_duplicates, actual_duplicates = duplicate_audit(candidates, {name: getattr(args, f"v1_{name}") for name in ("train", "validation", "test")})
    write_json(REPORTS / "reference_duplicate_report.json", reference_duplicates)
    write_json(REPORTS / "actual_v1_duplicate_report.json", actual_duplicates)
    write_json(REPORTS / "context_audit.json", history_audit)
    source.require(all(sha((ROOT / p).read_bytes()) == digest for p, digest in before.items()), "Protected source changed")
    report = {"candidate_status": "SINGLE_REVIEW_COMPLETE_NOT_FINAL_APPROVED", "conversations": len(candidates),
              **source.stats(candidates), "reviewer_results": {name: dict(Counter(row[f"검수_결과_{name}"] for row in reviews)) for name in review.REVIEWERS},
              "final_results": dict(Counter(row["최종_합의_결과"] for row in reviews)),
              "reference_revision": REVISION, "reference_files": len(manifest["files"]),
              "actual_v1_training_run_provenance": "UNVERIFIED: code recovered from Git, not identified from a v1 run manifest",
              "actual_v1_sample_builder": {"status": "PASS", "samples": len(built.samples), "statistics": built.statistics},
              "context": {"max_previous": max(len(s.history_texts) for s in built.samples), "verified_targets": len(history_audit),
                          "unapproved_single_review_context_ids": 0, "validation_test_inputs": 0},
              "actual_v1_duplicates": actual_duplicates["status"],
              "reference_near_utterances": len(reference_duplicates["near_utterance_candidates"]),
              "final_approval_policy_changed": False, "training_executed": False, "checkpoint_modified": False,
              "protected_sha256": before, "protected_files_unchanged": True,
              "outputs": [p.relative_to(ROOT).as_posix() for p in sorted(OUTPUT.glob("*.jsonl"))]}
    write_json(REPORTS / "preparation_result.json", report)
    print(json.dumps({key: report[key] for key in ("candidate_status", "conversations", "utterances", "phishing", "normal", "positive_labels", "actual_v1_sample_builder", "context", "actual_v1_duplicates", "protected_files_unchanged")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
