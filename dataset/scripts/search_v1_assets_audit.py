#!/usr/bin/env python3
"""Read-only targeted checkpoint/input/archive search with explicit access errors."""
import hashlib
import json
import os
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "reports/v2_pipeline_audit"


def main():
    profile = Path(os.environ["USERPROFILE"])
    roots = [ROOT, profile / "Downloads", profile / "Documents", profile / "OneDrive/문서",
             profile / ".codex/worktrees", profile / "OneDrive/Desktop/김해린", profile / ".cache/huggingface"]
    scopes, candidates = [], []
    names = {"koelectra_risk_v1.pt", "risk_speech_v1.pt", "labels.jsonl", "tuned.jsonl"}
    for base in roots:
        errors, found, seen, dirs = [], [], 0, 0
        def onerror(error):
            errors.append(dict(path=error.filename, error=str(error)))
        for directory, subs, files in os.walk(base, onerror=onerror, followlinks=False):
            subs[:] = [s for s in subs if s not in {".git", ".venv-v2", ".venv-ai", "node_modules", "__pycache__"}]
            dirs += 1
            for name in files:
                seen += 1
                path, lower = Path(directory)/name, name.lower()
                archive = lower.endswith((".zip", ".7z", ".tar", ".gz")) and any(k in lower for k in ("pic", "koelectra", "checkpoint", "backup", "risk_speech"))
                if lower not in names and not lower.endswith((".pt", ".pth", ".ckpt", ".safetensors")) and not archive:
                    continue
                try:
                    item = dict(path=str(path), bytes=path.stat().st_size,
                                kind="checkpoint_candidate" if lower.endswith((".pt", ".pth", ".ckpt")) else "named_input" if lower in names else "archive_or_other_weights")
                    if lower in names or item["kind"] == "checkpoint_candidate":
                        digest = hashlib.sha256()
                        with path.open("rb") as stream:
                            for chunk in iter(lambda: stream.read(1024*1024), b""):
                                digest.update(chunk)
                        item["sha256"] = digest.hexdigest()
                    if archive and lower.endswith(".zip"):
                        with zipfile.ZipFile(path) as z:
                            item["matching_zip_members"] = [dict(name=e.filename, bytes=e.file_size) for e in z.infolist()
                                if Path(e.filename).name.lower() in names or e.filename.lower().endswith((".pt", ".pth", ".ckpt"))]
                    found.append(item)
                    candidates.append(item)
                except (OSError, zipfile.BadZipFile) as error:
                    errors.append(dict(path=str(path), error=str(error)))
        scopes.append(dict(root=str(base), directories_scanned=dirs, files_seen=seen, candidates=len(found),
                           errors=errors, status="SCANNED_WITH_ERRORS" if errors else "SCANNED"))
    report = dict(scope=scopes, candidates=candidates,
                  trained_v1_checkpoint_status="NOT_FOUND" if not any(Path(r["path"]).name.lower() in {"koelectra_risk_v1.pt", "risk_speech_v1.pt"} for r in candidates) else "CANDIDATE_FOUND_REQUIRES_IDENTITY_CHECK",
                  limitation="Targeted related folders only. Access errors are not absence evidence. No claim about every disk, inaccessible folders, or other people's computers.")
    target = REPORTS / "local_asset_search.json"
    if target.exists() and not (REPORTS / "local_asset_search_initial_scope_error.json").exists():
        (REPORTS / "local_asset_search_initial_scope_error.json").write_bytes(target.read_bytes())
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(dict(scopes=[{k: v for k, v in s.items() if k != "errors"} | {"error_count": len(s["errors"])} for s in scopes], candidates=candidates), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
