#!/usr/bin/env python3
"""Summarize local asset availability against the preserved PR #35 evidence."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "reports/v2_pilot/ml_runtime"
REF = ROOT / "artifacts/v1_reference/pr35_9bab7e383928"
run = json.loads((REPORTS / "real_minibatch_result.json").read_text(encoding="utf-8"))
repro = json.loads((REF / "artifacts/risk_speech_ai/reports/reproducibility.json").read_text(encoding="utf-8"))
pr = json.loads((REPORTS / "pr35_metadata.json").read_text(encoding="utf-8"))


def command(args, cwd=ROOT):
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return {"command": args, "exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr}


assets = []
for name, relative, evidence in (
    ("KoELECTRA model definition", "risk_speech_ai/model.py", "Full base architecture random initialization forward passed; not trained-v1 validation"),
    ("Training CLI", "risk_speech_ai/train_cli.py", "Actual validation-only CLI passed for 136 v2 candidates; no --train"),
    ("Training implementation", "risk_speech_ai/training.py", "Imported successfully; train_model never called"),
    ("Dataset and collator", "risk_speech_ai/dataset.py", "Real CPU DataLoader generated 34 batches of size 4"),
    ("Tokenizer implementation", "risk_speech_ai/tokenization.py", "Pinned real tokenizer processed all 136 inputs"),
    ("Evaluation metrics", "risk_speech_ai/metrics.py", "Original metrics unit tests passed; no v1 model performance remeasured"),
    ("Evaluation CLI", "risk_speech_ai/evaluate_cli.py", "CLI --help checked below; real checkpoint evaluation not possible without weights"),
):
    path = REF / relative
    assets.append({"asset": name, "classification": "실제 실행 가능", "actual_path": str(path),
                   "origin": "Git에서 별도 복원 완료", "source_commit": pr["head_sha"],
                   "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "verification": evidence})
for name, item in repro["training_input_files"].items():
    relative = Path(item["path"].replace("\\", "/"))
    expected = ROOT / relative
    assets.append({"asset": f"Actual v1 training input: {name}", "classification": "아직 발견하지 못함",
                   "actual_path": None, "expected_project_path_from_PR35": str(expected), "exists": expected.exists(),
                   "expected_sha256_from_PR35": item["sha256"], "data_commit": repro["data_commit"],
                   "note": "Ignored original prepared artifact; source raw JSONL and manifest do not by themselves establish identical training input bytes."})
for relative in ("artifacts/risk_speech_ai/koelectra_risk_v1.pt", "checkpoints/risk_speech_v1.pt"):
    expected = ROOT / relative
    assets.append({"asset": "Actual trained v1 checkpoint", "classification": "아직 발견하지 못함", "actual_path": None,
                   "expected_project_path_from_PR35": str(expected), "exists": expected.exists(),
                   "expected_sha256_from_PR35": repro["checkpoint"]["sha256"], "expected_bytes_from_PR35": repro["checkpoint"]["bytes"],
                   "note": "PR handoff states weights are not in Git or LFS and external handoff was not completed. This is documentary evidence, not a local checksum verification."})
assets += [
    {"asset": "Actual TRAIN/VALIDATION/TEST split", "classification": "아직 발견하지 못함", "actual_path": None,
     "note": "PR35 reports TRAIN IN-SAMPLE evaluation and no independent validation/test. splits.py provides a future planning function, not the historical split manifest."},
    {"asset": "Future split planning implementation", "classification": "참고용 코드만 존재",
     "actual_path": str(REF / "risk_speech_ai/splits.py"), "note": "Source tests pass; no new split or synthetic validation/test data was generated."},
    {"asset": "Historic training-use manifest", "classification": "참고용 자료만 존재",
     "actual_path": str(REF / "risk_speech_ai/data_review_manifest_20261027.json"),
     "note": "Recovered Git manifest. Original v1 prepared labels/tuned file hashes still require verification."},
    {"asset": "Older local Git implementation", "classification": "Git에서 복원 가능; 기존 별도 스냅샷 유지",
     "actual_path": str(ROOT / "artifacts/v1_reference/958c30e4ac6c"),
     "note": "This run uses the newer PR35 snapshot, not the older snapshot."},
]
cache = json.loads((REPORTS / "tokenizer_cache.json").read_text(encoding="utf-8"))
assets.append({"asset": "Pinned actual tokenizer/config assets", "classification": "실제 실행 가능",
               "actual_path": str(ROOT / cache["snapshot"]), "revision": cache["revision"],
               "vocabulary_matches_PR35_report": run["tokenizer"]["vocabulary_fingerprint_matches_PR35_report"],
               "note": "Public base tokenizer assets only; no trained v1 model weights downloaded."})
help_result = command([sys.executable, "-B", "-X", "utf8", "-m", "risk_speech_ai.evaluate_cli", "--help"], cwd=REF)
git_evidence = {
    "branch": command(["git", "branch", "-avv"]),
    "worktrees": command(["git", "worktree", "list", "--porcelain"]),
    "all_lfs_files": command(["git", "lfs", "ls-files", "--all"]),
    "pr35_commit_in_local_object_database": command(["git", "cat-file", "-t", pr["head_sha"]]),
    "original_v1_data_commit_in_local_object_database": command(["git", "cat-file", "-t", repro["data_commit"]]),
}
report = {"pr35": {key: pr[key] for key in ("url", "title", "state", "merged", "head_sha")},
          "assets": assets, "evaluation_CLI_help": help_result, "git_and_lfs_evidence": git_evidence,
          "search_scope": [str(ROOT), "all locally cached Git refs/history and LFS listing", "current Git worktree list",
                           "connected GitHub PR35 recursive tree, source and handoff documents",
                           "accessible relevant Downloads, OneDrive documents/Codex, .codex/worktrees, default Hugging Face cache"],
          "search_limitation": "Not a scan of every disk or other people's computers. No checkpoint/source files were moved or overwritten. Android NER/STT LFS models are not risk-classification v1 weights.",
          "v1_checkpoint_loaded": False, "actual_v1_train_input_duplicate_check": "NOT_VERIFIED_ORIGINAL_INPUT_FILES_MISSING",
          "new_data_generated": False, "training_executed": False}
(REPORTS / "v1_asset_inventory.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"assets": len(assets), "evaluate_cli_help_exit": help_result["exit_code"],
                  "cuda_available": run["environment"]["cuda_available"],
                  "tokenizer_fingerprint_matches_PR35": run["tokenizer"]["vocabulary_fingerprint_matches_PR35_report"],
                  "checkpoint_found": any(a.get("exists") for a in assets if a["asset"] == "Actual trained v1 checkpoint")}, ensure_ascii=False, indent=2))
