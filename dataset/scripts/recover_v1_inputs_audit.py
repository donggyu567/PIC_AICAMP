#!/usr/bin/env python3
"""Recover historical input bytes only when both published SHA-256s match.

No synthetic data or new human approval is generated. Historical preparation
logic runs in memory on Git-blob-verified source snapshots. Its output is saved
as recovered v1 input only after matching the previously recorded hashes.
"""
import hashlib
import json
import os
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "reports/v2_pipeline_audit"
REF = ROOT / "artifacts/v1_reference/pr35_9bab7e383928"
OUT = ROOT / "artifacts/v1_recovered_8faa6a7eebfe"
COMMIT = "8faa6a7eebfe95c7ac7fe6c6077a49ebf31f958f"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def blob(data):
    return hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest()


def save_new(path, data):
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError(f"Refuse to overwrite {path}")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(data)


def main():
    tree = json.loads((REPORTS / "v1_data_commit_tree.json").read_text(encoding="utf-8"))
    assert tree["sha"] == COMMIT and tree["truncated"] is False
    by_path = {e["path"]: e for e in tree["tree"]}
    payloads = {r["path"]: r for r in json.loads((REPORTS / "recovered_source_payloads.json").read_text(encoding="utf-8"))}
    manifest_path = REF / "risk_speech_ai/data_review_manifest_20261027.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    required = {e["path"] for e in manifest if e["id"] not in {f"N{i:04d}" for i in range(15, 20)}}
    sources, records = {}, []
    for path in sorted(required):
        expected = by_path[path]
        local = ROOT / path
        original = local.read_bytes() if local.is_file() else None
        if original is not None and blob(original) == expected["sha"]:
            data, origin = original, "existing_local_exact_git_blob"
        else:
            payload = payloads[path]
            assert payload["encoding"] == "utf-8" and payload["sha"] == expected["sha"]
            data, origin = payload["content"].encode("utf-8"), "GitHub_original_commit_blob"
        assert blob(data) == expected["sha"] and len(data) == expected["size"], f"Blob mismatch: {path}"
        target = OUT / "source_snapshot" / path
        save_new(target, data)
        sources[path] = [json.loads(line) for line in data.decode("utf-8-sig").splitlines() if line.strip()]
        records.append(dict(source_path=path, restored_path=str(target), git_blob=expected["sha"],
                            sha256=sha(data), bytes=len(data), origin=origin))
    sys.path.insert(0, str(REF))
    from risk_speech_ai import prepare_training_inputs as preparation
    from risk_speech_ai.training_data import build_training_samples
    preparation._source_rows = lambda commit, path, cid: [row for row in sources[path] if row.get("conversation_id") == cid]
    labels, texts, pending = preparation.prepare_team_approved(manifest, COMMIT)
    # The historical writer used Path.write_text(newline=None) on Windows,
    # which emits CRLF. Reproduce serialization as well as row content.
    encode = lambda rows: "".join(json.dumps(r, ensure_ascii=False)+os.linesep for r in rows).encode("utf-8")
    output = {"labels": encode(labels), "tuned": encode(texts)}
    repro = json.loads((REF / "artifacts/risk_speech_ai/reports/reproducibility.json").read_text(encoding="utf-8"))
    comparison = {name: dict(expected_sha256=repro["training_input_files"][name]["sha256"],
                             actual_sha256=sha(data), bytes=len(data),
                             exact_match=sha(data) == repro["training_input_files"][name]["sha256"])
                  for name, data in output.items()}
    exact = all(r["exact_match"] for r in comparison.values())
    report = dict(status="RECOVERED_EXACT_SHA256" if exact else "NOT_FOUND_EXACT_BYTES_RECONSTRUCTION_MISMATCH",
                  source_commit=COMMIT, source_tree_truncated=False, source_files=records,
                  preparation_code_sha256=sha((REF / "risk_speech_ai/prepare_training_inputs.py").read_bytes()),
                  manifest_sha256=sha(manifest_path.read_bytes()), output=comparison,
                  rows=len(labels), conversations=len({r["conversation_id"] for r in labels}),
                  pending_reasons=dict(Counter({reason: sum(r.get("excluded_utterance_count", 1) for r in pending if r["reason"] == reason)
                                                for reason in {r["reason"] for r in pending}})),
                  serialization=dict(encoding="utf-8", newline=repr(os.linesep), json_ensure_ascii=False),
                  human_approval_assigned=False, new_synthetic_data_generated=False,
                  note="Historical status fields are reconstructed, not new approval; exact original bytes claimed only when both published hashes match. Runtime source retrieval was replaced in memory only; existing repository files are unchanged.")
    if exact:
        for name, data in output.items():
            path = OUT / "prepared" / f"{name}.jsonl"
            save_new(path, data)
            report["output"][name]["path"] = str(path)
        built = build_training_samples(labels, texts)
        report["builder_statistics"] = built.statistics
        assert len(built.samples) == report["rows"] == 1460 and report["conversations"] == 68
    (REPORTS / "v1_input_recovery.json").write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "source_files"}, ensure_ascii=False, indent=2))
    return int(not exact)


if __name__ == "__main__":
    raise SystemExit(main())
