#!/usr/bin/env python3
"""Select and inspect the v2 delivery without staging unrelated workspace files."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "reports/v2_pilot/git_delivery_manifest.json"
SCRIPT_NAMES = (
    "restore_pilot.py", "prepare_pilot_review.py", "finalize_pilot_review.py",
    "prepare_v2_training_candidate.py", "smoke_v2_training_candidate.py",
    "cache_v2_tokenizer.py", "validate_v2_real_minibatch.py", "report_v2_ml_assets.py",
    "audit_v2_commit.py",
)
RULES = {
    "private_key": re.compile(r"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----"),
    "github_token": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{50,})\b"),
    "openai_key": re.compile(r"(?<![\w-])sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{24,}"),
    "aws_access_key": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "credential_url": re.compile(r"https?://[^\s/@]+:[^\s/@]+@"),
    "korean_mobile": re.compile(r"(?<![A-Za-z0-9])01[016789][- ]?\d{3,4}[- ]?\d{4}(?![A-Za-z0-9])"),
    "rrn": re.compile(r"(?<![A-Za-z0-9])\d{6}[- ]?[1-4]\d{6}(?![A-Za-z0-9])"),
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
}


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def selection():
    selected = {ROOT / name for name in (".gitignore", ".gitattributes", "KOELECTRA_V2_READINESS.md")}
    selected.update(ROOT / "dataset/scripts" / name for name in SCRIPT_NAMES)
    for directory in (
        "inputs/pilot_sources", "dataset/review/v2_pilot", "dataset/04. processed/v2_pilot/training_candidate",
        "artifacts/v1_reference", "tests", "reports/v2_pilot",
    ):
        for path in (ROOT / directory).rglob("*"):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            relative = path.relative_to(ROOT).as_posix()
            if "/approval_" in relative or path.name == "execution_initial_attempt.json":
                continue
            if directory == "tests" and not path.name.startswith("test_"):
                continue
            selected.add(path)
    selected.add(ROOT / "dataset/04. processed/v2_pilot/pilot_canonical.jsonl")
    selected.discard(MANIFEST)
    return sorted(selected)


def scan(paths, *, staged=False):
    findings, files = [], []
    for path in paths:
        relative = path.relative_to(ROOT).as_posix()
        data = git("show", ":" + relative) if staged else path.read_bytes()
        if b"\0" in data or len(data) > 1_000_000:
            findings.append({"path": relative, "rule": "binary_or_over_1MB"})
            continue
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            findings.append({"path": relative, "rule": "non_utf8_binary"})
            continue
        for number, line in enumerate(text.splitlines(), 1):
            for rule, pattern in RULES.items():
                if pattern.search(line):
                    findings.append({"path": relative, "line": number, "rule": rule})
        files.append({"path": relative, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    return files, findings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-staged", action="store_true")
    args = parser.parse_args()
    paths = selection()
    if args.verify_staged:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        staged_names = git("diff", "--cached", "--name-only", "-z").decode("utf-8").split("\0")[:-1]
        expected = {record["path"] for record in manifest["files"]} | {MANIFEST.relative_to(ROOT).as_posix()}
        assert set(staged_names) == expected, "Staged selection differs from reviewed manifest"
        assert not git("diff", "--cached", "--name-only", "--diff-filter=MD"), "Existing tracked files must be unchanged"
        files, findings = scan([ROOT / name for name in staged_names], staged=True)
        assert not findings, json.dumps(findings, ensure_ascii=False)
        for record in manifest["files"]:
            staged = git("show", ":" + record["path"])
            assert hashlib.sha256(staged).hexdigest() == record["sha256"], record["path"]
            assert staged == (ROOT / record["path"]).read_bytes(), "Evidence bytes changed during staging"
        print(json.dumps({"staged_files": len(files), "secret_or_PII_findings": len(findings),
                          "exact_evidence_bytes_preserved": True, "existing_v1_files_modified": False}, indent=2))
        return
    assert not git("diff", "HEAD", "--name-only", "--diff-filter=MD"), "Review pre-existing tracked modifications before proceeding"
    files, findings = scan(paths)
    assert not findings, json.dumps(findings, ensure_ascii=False)
    run = json.loads((ROOT / "reports/v2_pilot/ml_runtime/real_minibatch_result.json").read_text(encoding="utf-8"))
    assert run["status"].startswith("PASS") and run["source_tests"]["passed"] == 48
    assert run["check_counts"] == {"passed": 16, "failed": 0}
    assert all(hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest for name, digest in run["protected_sha256"].items())
    with (ROOT / "dataset/review/v2_pilot/human_review_working.csv").open(encoding="utf-8-sig", newline="") as stream:
        reviews = list(csv.DictReader(stream))
    assert len(reviews) == 136 and all(row["검수_결과_임정윤"] == "승인" and row["검수_결과_김해린"] == "미승인" and row["최종_합의_결과"] == "미승인" for row in reviews)
    candidates = [json.loads(line) for line in (ROOT / "dataset/04. processed/v2_pilot/training_candidate/pilot_single_review_train_candidate.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(candidates) == 16 and all(c["split"] == "train" and c["review_preparation"]["final_approved"] is False for c in candidates)
    report = {
        "branch": git("branch", "--show-current").decode().strip(), "base_commit": git("rev-parse", "HEAD").decode().strip(),
        "purpose": "Commit and push explicitly authorized v2 pilot readiness work; no training, PR or merge",
        "files": files, "manifest_itself": MANIFEST.relative_to(ROOT).as_posix(), "total_bytes_excluding_manifest": sum(f["bytes"] for f in files),
        "scan": {"scanned_files": len(files), "credential_or_PII_pattern_findings": findings,
                 "scope": "UTF-8 staged-candidate text; private keys, common tokens, credential URLs, Korean mobile/RRN/email patterns and binary/size checks",
                 "authorized_work_context": "Requested reviewer names and user-provided workspace paths retained as review/provenance evidence; synthetic transcripts only"},
        "review_status": {"임정윤_승인": 136, "김해린_미승인": 136, "최종합의_미승인": 136, "two_person_final_policy_unchanged": True},
        "tests": {"project_unit_tests_passed": 22, "PR35_non_training_tests_passed": run["source_tests"]["passed"],
                  "real_runtime_checks_passed": run["check_counts"]["passed"], "minibatches": run["minibatch"]["batches_generated"],
                  "batch_size": run["minibatch"]["batch_size"], "training_executed": False},
        "excluded": [".venv-v2/ and other environments", "artifacts/v2_runtime_assets/ tokenizer/model cache", "__pycache__ and temporary files",
                     ".env and credentials", "checkpoint/model binaries", "phishing_candidate_research_jeongyun_202609w4.md (unrelated pre-existing research)",
                     "dataset/04. processed/v2_pilot/approval_*/ empty intermediate exports", "reports/v2_pilot/approval_*/ superseded diagnostics",
                     "reports/v2_pilot/training_readiness/execution_initial_attempt.json (superseded environment-error attempt)"],
        "existing_v1_tracked_files_modified": False,
        "pinned_reference_note": "New isolated source fixtures needed to reproduce v2 adapter/runtime checks; existing v1 originals/checkpoints unchanged",
    }
    MANIFEST.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"candidate_files_plus_manifest": len(files) + 1, "bytes": report["total_bytes_excluding_manifest"],
                      "secret_or_PII_findings": len(findings), "branch": report["branch"],
                      "final_approved": False}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
