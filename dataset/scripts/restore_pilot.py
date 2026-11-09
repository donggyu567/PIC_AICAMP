#!/usr/bin/env python3
"""Restore the supplied v2 pilot without generating, relabeling, or training data.

Standard library only. --check-only validates the existing artifact against the
TXT evidence and never repairs it silently. Source hashes are pinned deliberately.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
import unicodedata
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCES = ROOT / "inputs" / "pilot_sources"
OUTPUT = ROOT / "dataset" / "04. processed" / "v2_pilot"
REPORTS = ROOT / "reports" / "v2_pilot"
FILENAMES = [f"붙여넣은 텍스트(1)({i}).txt" for i in (2, 3, 4)]
HASHES = [
    "ebd06d24245c60dcf79295a6505163a936e967f4483a40e8572d08c7af62bba7",
    "c4e219509536d10aef5059ac8dd16b88ec010dbc4de53eeca07ca5e3e55bd30e",
    "cb7f5b6155b225c592ade35c3de24b6d90e7d6d81799e9c6faa3a9a89a753141",
]
LABELS = (
    "institution_impersonation", "money_transfer", "personal_information",
    "app_installation", "secrecy", "threat_pressure", "loan_fraud",
    "information_probing",
)
EXPECTED_LABELS = dict(zip(LABELS, (10, 3, 4, 7, 5, 3, 3, 2)))
IDS = [f"SYN2-TRAIN-{i:04}" for i in range(1, 17)]
REVISED_IDS = [IDS[i - 1] for i in (5, 6, 7, 9, 10, 11, 15)]
PATCH_TEXT = "네, 그럼 이만 끊겠습니다."
CONVERSATION_FIELDS = {
    "synthetic_id", "is_synthetic", "source_kind", "actual_call", "split",
    "split_version", "scenario_family_id", "scenario_id", "variant_id",
    "primary_type", "scenario_summary", "generation_model", "prompt_version",
    "review_status", "review_flags", "utterances",
}
UTTERANCE_FIELDS = {
    "utterance_id", "speaker", "text", "is_phishing", "labels", "label_rationale",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def unique_keys(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def parse_json(text):
    return json.loads(text, object_pairs_hook=unique_keys)


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def jsonl_bytes(rows):
    return ("\n".join(json.dumps(row, ensure_ascii=False, separators=(",", ":"))
                      for row in rows) + "\n").encode("utf-8")


def stats(rows):
    utterances = [u for row in rows for u in row["utterances"]]
    counts = Counter(label for u in utterances for label in u["labels"])
    phishing = sum(u["is_phishing"] is True for u in utterances)
    return {
        "conversations": len(rows), "utterances": len(utterances),
        "phishing": phishing, "normal": len(utterances) - phishing,
        "positive_labels": sum(counts.values()),
        "labels": {label: counts[label] for label in LABELS},
    }


def restore(source_dir=SOURCES, original_dir=None):
    require(sorted(p.name for p in source_dir.rglob("*.txt")) == sorted(FILENAMES),
            "Expected exactly the three supplied TXT sources")
    batches, source_info = [], []
    for filename, digest in zip(FILENAMES, HASHES):
        path = source_dir / filename
        data = path.read_bytes()
        require(sha(data) == digest, f"Source SHA-256 mismatch: {filename}")
        info = {"file": filename, "bytes": len(data), "sha256": digest}
        if original_dir is not None:
            matches = list(original_dir.rglob(filename))
            require(len(matches) == 1, f"Expected one original: {filename}")
            require(matches[0].read_bytes() == data, f"Original/copy mismatch: {filename}")
            info["original_copy_verified"] = True
        entries, in_jsonl = [], False
        for line_number, line in enumerate(data.decode("utf-8").splitlines(), 1):
            if line.strip() == "```jsonl":
                require(not in_jsonl, f"Nested JSONL fence: {filename}:{line_number}")
                in_jsonl = True
            elif line.strip() == "```" and in_jsonl:
                in_jsonl = False
            elif in_jsonl and line.strip():
                row = parse_json(line)
                require(isinstance(row, dict), "Source JSONL root must be an object")
                entries.append((row, {"file": filename, "line": line_number}))
        require(not in_jsonl, f"Unclosed JSONL block: {filename}")
        require(len({row["synthetic_id"] for row, _ in entries}) == len(entries),
                f"Duplicate IDs in {filename}")
        source_info.append(info)
        batches.append(entries)
    require([row["synthetic_id"] for row, _ in batches[0]] == IDS[:4], "First batch IDs")
    require([row["synthetic_id"] for row, _ in batches[1]] == IDS[4:], "Second batch IDs")
    require([row["synthetic_id"] for row, _ in batches[2]] == REVISED_IDS, "Revision IDs")

    rows, versions = {}, defaultdict(list)
    for row, location in batches[0] + batches[1]:
        rows[row["synthetic_id"]] = copy.deepcopy(row)
        versions[row["synthetic_id"]].append(location)
    # This edit exists as an explicit text instruction, outside the JSONL block.
    instruction = (source_dir / FILENAMES[1]).read_text(encoding="utf-8")
    require('SYN2-TRAIN-0003, utterance_id=10\ntext: "' + PATCH_TEXT +
            '"\nis_phishing: false\nlabels: []' in instruction, "Missing explicit 0003-10 patch")
    target = rows[IDS[2]]["utterances"][9]
    before = copy.deepcopy(target)
    target.update(text=PATCH_TEXT, is_phishing=False, labels=[])
    patch = {"synthetic_id": IDS[2], "utterance_id": 10,
             "source": {"file": FILENAMES[1], "lines": [6, 7, 8, 9]},
             "before": before, "after": copy.deepcopy(target)}
    baseline = stats(list(rows.values()))
    differences = []
    for row, location in batches[2]:
        cid = row["synthetic_id"]
        old = rows[cid]
        require(old["generation_model"] == row["generation_model"], f"Generator changed: {cid}")
        require(len(old["utterances"]) == len(row["utterances"]), f"Utterance count changed: {cid}")
        changes = []
        for first, second in zip(old["utterances"], row["utterances"]):
            require(first["utterance_id"] == second["utterance_id"], f"ID changed: {cid}")
            fields = {key: {"before": first.get(key), "after": second.get(key)}
                      for key in sorted(first.keys() | second.keys())
                      if first.get(key) != second.get(key)}
            if fields:
                changes.append({"utterance_id": second["utterance_id"], "fields": fields})
        declared = row["revision_history"][-1]["changed_utterance_ids"]
        actual = [change["utterance_id"] for change in changes]
        differences.append({"synthetic_id": cid, "declared_changed_ids": declared,
                            "actual_changed_ids": actual,
                            "unlisted_changed_ids": sorted(set(actual) - set(declared)),
                            "declared_but_unchanged_ids": sorted(set(declared) - set(actual)),
                            "changes": changes})
        rows[cid] = copy.deepcopy(row)
        versions[cid].append(location)
    manifest = {
        "source_files": source_info,
        "policy": "Initial 4 + next 12 + explicit 0003-10 patch + latest 7 full replacements; JSON bodies take precedence over narrative tables.",
        "human_approved": False, "training_performed": False, "git_push_performed": False,
        "generation_model_note": "Source metadata preserved verbatim; original execution environments are unverified.",
        "versions": dict(versions), "explicit_patch": patch,
        "revision_differences": differences, "before_latest_revision": baseline,
    }
    return [rows[cid] for cid in IDS], manifest


def validate(rows, expected=None):
    require(isinstance(rows, list) and len(rows) == 16, "Expected 16 conversations")
    require([row.get("synthetic_id") for row in rows] == IDS, "Conversation IDs/order/uniqueness")
    families, scenarios = set(), set()
    for index, row in enumerate(rows, 1):
        cid = row["synthetic_id"]
        require(CONVERSATION_FIELDS <= row.keys(), f"Missing conversation fields: {cid}")
        require(not (row.keys() - CONVERSATION_FIELDS - {"revision_history", "fictional_organization"}),
                f"Unexpected conversation fields: {cid}")
        for key, value in {"is_synthetic": True, "actual_call": False}.items():
            require(row[key] is value, f"Invalid {key}: {cid}")
        for key, value in {"source_kind": "llm_simulation", "split": "train",
                           "split_version": "v2-pilot-1", "prompt_version": "v2-pilot-1",
                           "review_status": "generated", "variant_id": "original"}.items():
            require(row[key] == value, f"Invalid {key}: {cid}")
        require(row["scenario_family_id"] == f"FAM2-TRAIN-{index:04}", f"Family mismatch: {cid}")
        for key in ("scenario_summary", "scenario_id", "generation_model"):
            require(isinstance(row[key], str) and row[key].strip(), f"Empty {key}: {cid}")
        require(row["primary_type"] is None or row["primary_type"] in LABELS, f"Primary type: {cid}")
        require(isinstance(row["review_flags"], list) and row["review_flags"] and
                all(isinstance(flag, str) and flag.strip() for flag in row["review_flags"]), f"Review flags: {cid}")
        families.add(row["scenario_family_id"])
        scenarios.add(row["scenario_id"])
        for revision in row.get("revision_history", []):
            require(revision.get("human_approved") is False, f"Unexpected human approval: {cid}")
            require(isinstance(revision.get("revision_model"), str) and revision["revision_model"], f"Revision model: {cid}")
        if "fictional_organization" in row:
            require(row["fictional_organization"].get("is_fictional") is True, f"Fictional organization: {cid}")
        utterances = row["utterances"]
        require(isinstance(utterances, list) and len(utterances) == (10 if index <= 4 else 8), f"Utterance count: {cid}")
        for number, u in enumerate(utterances, 1):
            location = f"{cid}:{number}"
            require(set(u) == UTTERANCE_FIELDS, f"Utterance fields: {location}")
            require(type(u["utterance_id"]) is int and u["utterance_id"] == number, f"Utterance IDs: {location}")
            require(u["speaker"] in {"speaker_A", "speaker_B", "unknown"}, f"Speaker: {location}")
            for key in ("text", "label_rationale"):
                require(isinstance(u[key], str) and u[key].strip(), f"Empty {key}: {location}")
            require(type(u["is_phishing"]) is bool, f"Boolean: {location}")
            labels = u["labels"]
            require(isinstance(labels, list) and all(isinstance(label, str) and label in LABELS for label in labels), f"Labels: {location}")
            require(len(labels) == len(set(labels)), f"Duplicate labels: {location}")
            require(u["is_phishing"] or labels == [], f"Normal utterance has labels: {location}")
    require(len(families) == 16 and len(scenarios) == 16, "Duplicate family/scenario IDs")
    counts = stats(rows)
    require((counts["utterances"], counts["phishing"], counts["normal"], counts["positive_labels"]) ==
            (136, 34, 102, 37), "Canonical counts differ from supplied JSON bodies")
    require(counts["labels"] == EXPECTED_LABELS, "Canonical label counts differ")
    if expected is not None:
        require(rows == expected, "Canonical content differs from TXT evidence (including patch/latest revisions)")
    return counts


def normalize(text):
    text = unicodedata.normalize("NFKC", text).casefold()
    return "".join(c for c in text if not c.isspace() and not unicodedata.category(c).startswith("P"))


def duplicate_report(rows):
    pilot = [(row["synthetic_id"], u["utterance_id"], u["text"])
             for row in rows for u in row["utterances"]]
    local, scanned = {}, []
    # Include all locally available raw, staging and masked v1 representations;
    # schema examples and restored v2 output are intentionally excluded.
    for dirname in ("01. raw", "02. staging", "03. masked"):
        for path in sorted((ROOT / "dataset" / dirname).rglob("*")):
            if not path.is_file() or path.suffix not in {".json", ".jsonl"}:
                continue
            data = path.read_bytes()
            text = data.decode("utf-8-sig")
            entries = [parse_json(text)] if path.suffix == ".json" else [parse_json(line) for line in text.splitlines() if line.strip()]
            scanned.append({"file": path.relative_to(ROOT).as_posix(), "sha256": sha(data)})
            for entry in entries:
                if all(key in entry for key in ("conversation_id", "utterance_id", "text")):
                    require(isinstance(entry["text"], str), f"Invalid comparison text: {path}")
                    key = (entry["conversation_id"], entry["utterance_id"], entry["text"])
                    local[key] = True
    def groups(entries, normalized):
        grouped = defaultdict(list)
        for cid, uid, text in entries:
            grouped[normalize(text) if normalized else text].append(f"{cid}:{uid}")
        return [refs for refs in grouped.values() if len(refs) > 1]
    index = defaultdict(list)
    for cid, uid, text in local:
        index[normalize(text)].append((cid, uid, text))
    matches = []
    for cid, uid, text in pilot:
        for other_cid, other_uid, other_text in index.get(normalize(text), []):
            matches.append({"pilot": f"{cid}:{uid}", "local_v1": f"{other_cid}:{other_uid}",
                            "kind": "exact" if text == other_text else "normalized"})
    transcripts = {row["synthetic_id"]: normalize("\n".join(u["text"] for u in row["utterances"])) for row in rows}
    near = []
    for (first, a), (second, b) in combinations(transcripts.items(), 2):
        similarity = SequenceMatcher(None, a, b, autojunk=False).ratio()
        if similarity >= 0.90:
            near.append({"first": first, "second": second, "similarity": round(similarity, 6)})
    # A v1 conversation may have multiple text representations. Compare each
    # scanned file's own conversation instead of concatenating those versions.
    v1_conversations = set()
    raw_groups = defaultdict(dict)
    for item in scanned:
        path = ROOT / item["file"]
        if path.suffix == ".json":
            row = parse_json(path.read_text(encoding="utf-8-sig"))
            if all(k in row for k in ("conversation_id", "utterance_id", "text")):
                raw_groups[row["conversation_id"]][row["utterance_id"]] = row["text"]
        else:
            grouped = defaultdict(dict)
            for line in path.read_text(encoding="utf-8-sig").splitlines():
                if not line.strip():
                    continue
                row = parse_json(line)
                if all(k in row for k in ("conversation_id", "utterance_id", "text")):
                    grouped[row["conversation_id"]][row["utterance_id"]] = row["text"]
            for cid, entries in grouped.items():
                v1_conversations.add((cid, normalize("\n".join(entries[i] for i in sorted(entries)))))
    for cid, entries in raw_groups.items():
        v1_conversations.add((cid, normalize("\n".join(entries[i] for i in sorted(entries)))))
    near_v1 = []
    for cid, text in transcripts.items():
        for other_cid, other_text in sorted(v1_conversations):
            matcher = SequenceMatcher(None, text, other_text, autojunk=False)
            if matcher.real_quick_ratio() >= 0.90 and matcher.quick_ratio() >= 0.90:
                ratio = matcher.ratio()
                if ratio >= 0.90:
                    near_v1.append({"pilot": cid, "local_v1": other_cid, "similarity": round(ratio, 6)})
    return {"normalization": "NFKC + casefold; remove whitespace/punctuation",
            "similarity_method": "difflib.SequenceMatcher, autojunk=False, threshold >= 0.90",
            "local_files_scanned": scanned, "unique_local_utterance_versions": len(local),
            "unique_local_conversation_versions": len(v1_conversations),
            "pilot_exact_utterance_groups": groups(pilot, False),
            "pilot_normalized_utterance_groups": groups(pilot, True),
            "pilot_similar_conversations": near, "local_v1_utterance_matches": matches,
            "local_v1_similar_conversations": near_v1,
            "limitation": "Only locally available files were compared; semantic duplication and unavailable v1 data remain unverified. Candidates were preserved, not deleted."}


def warnings(manifest):
    result = [
        {"code": "SOURCE_TABLE_COUNTS", "detail": "Final TXT claims 32 phishing / 104 normal / 35 positive labels; JSON bodies yield 34 / 102 / 37. JSON is preserved."},
        {"code": "SOURCE_TABLE_LABELS", "detail": "Final TXT claims app_installation=6, secrecy=4; JSON bodies yield 7 and 5."},
        {"code": "SOURCE_0006_7", "detail": "Final narrative says 0006-7 became normal; final JSON still directly requests secrecy and retains true/[secrecy]. Preserved for human review."},
        {"code": "HUMAN_REVIEW_PENDING", "detail": "All records remain generated and unapproved. See source review notes, especially 0005-7, 0006, 0007, 0009-5, 0010-5, 0011 and 0015. Generator execution provenance remains unverified."},
    ]
    for diff in manifest["revision_differences"]:
        if diff["unlisted_changed_ids"] or diff["declared_but_unchanged_ids"]:
            result.append({"code": "REVISION_HISTORY_MISMATCH", "synthetic_id": diff["synthetic_id"],
                           "unlisted_changed_ids": diff["unlisted_changed_ids"],
                           "declared_but_unchanged_ids": diff["declared_but_unchanged_ids"]})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--original-dir", type=Path, help="Also verify original TXT files against copies")
    args = parser.parse_args()
    try:
        expected, manifest = restore(original_dir=args.original_dir)
        validate(expected)
        path = OUTPUT / "pilot_canonical.jsonl"
        if not args.check_only:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(jsonl_bytes(expected))
        data = path.read_bytes()
        lines = data.decode("utf-8").splitlines()
        require(len(lines) == 16 and all(line.strip() for line in lines), "Expected 16 nonblank JSONL lines")
        rows = [parse_json(line) for line in lines]
        counts = validate(rows, expected)
        require(data == jsonl_bytes(rows), "Expected deterministic UTF-8 JSONL with LF and final newline")
        duplicates = duplicate_report(rows)
        manifest["canonical_file"] = path.relative_to(ROOT).as_posix()
        manifest["canonical_sha256"] = sha(data)
        report = {"status": "PASS_WITH_REVIEW_NOTES", "structural_errors": [],
                  "counts": counts, "warnings": warnings(manifest),
                  "per_conversation": [{"synthetic_id": row["synthetic_id"], **stats([row])} for row in rows],
                  "canonical_sha256": sha(data), "python_version": sys.version.split()[0],
                  "checks": ["Pinned source SHA-256", "Source precedence and explicit patch", "Strict JSON and duplicate keys", "Schema and ID continuity", "Synthetic/train/generated metadata", "Label types and consistency", "Source equality and preserved model metadata", "Counts from JSON bodies", "Local duplicate candidates"],
                  "human_approved": False, "training_performed": False, "git_push_performed": False}
        report["duplicate_summary"] = {
            key: len(duplicates[key]) for key in (
                "local_files_scanned", "pilot_exact_utterance_groups",
                "pilot_normalized_utterance_groups", "pilot_similar_conversations",
                "local_v1_utterance_matches", "local_v1_similar_conversations",
            )
        }
        write_json(REPORTS / "restoration_manifest.json", manifest)
        write_json(REPORTS / "validation_report.json", report)
        write_json(REPORTS / "duplicate_report.json", duplicates)
        markdown = [
            "# v2 파일럿 정본 복원·검증 결과", "",
            "자동 구조 검증 통과. 사람 검수 및 학습 사용 승인은 미완료입니다.", "",
            "- 정본: `dataset/04. processed/v2_pilot/pilot_canonical.jsonl` (UTF-8, 1대화/1행)",
            "- TXT 3개를 SHA-256으로 고정하고, 4대화 + 신규 12대화 + 0003-10 명시 수정 + 최신 7대화 전체 교체 순서로 복원했습니다.",
            "- 0003-10은 `네, 그럼 이만 끊겠습니다.`로 반영했습니다. 그 외 임의 문장·라벨 수정은 없습니다.",
            "- 원본 generation_model, revision_history 및 generated 상태를 보존했습니다. 원본 모델의 실제 실행 환경은 검증하지 않았습니다.",
            "- 원본 TXT와 기존 데이터는 수정하지 않았습니다. 모델 학습·Git push는 수행하지 않았습니다.", "",
            "| 항목 | JSON 본문 재계산 | 마지막 TXT 집계표 |", "|---|---:|---:|",
            "| 대화 | 16 | 16 |", "| 발화 | 136 | 136 |",
            "| 피싱 발화 | 34 | 32 |", "| 정상 발화 | 102 | 104 |", "| 양성 라벨 합계 | 37 | 35 |", "",
            "멀티라벨 때문에 양성 라벨 합계와 피싱 발화 수는 다릅니다.", "",
            "| 라벨 | JSON 본문 재계산 |", "|---|---:|",
        ]
        markdown += [f"| {label} | {count} |" for label, count in counts["labels"].items()]
        markdown += ["", "## 사람 검수 사항", "",
                     "- 최신 설명표는 0006-7의 피싱 라벨을 제거했다고 하지만 JSON에는 비밀 유지 요구와 true/[secrecy]가 남아 있습니다.",
                     "- 최신 집계표의 app_installation=6·secrecy=4와 달리 본문은 각각 7·5입니다. 집계표에 맞추려고 본문을 변경하지 않았습니다."]
        for warning in report["warnings"]:
            if warning["code"] == "REVISION_HISTORY_MISMATCH":
                markdown.append(f"- {warning['synthetic_id']}: 수정 이력에 없는 실제 변경 발화={warning['unlisted_changed_ids']}; 이력에는 있지만 본문 차이가 없는 발화={warning['declared_but_unchanged_ids']}. 상세 전후값은 restoration_manifest.json에 있습니다.")
        python_command = "& '" + sys.executable.replace("'", "''") + "' -B"
        markdown += ["- 원본이 지정한 경계 사례(0005-7 앱 실행, 0006 사칭 전제, 0007 조직 사칭, 0009-5 대출 미끼, 0010-5 결제, 0011 탐색, 0015 가상 신청 절차)를 검수해야 합니다.", "",
                     "## 중복 검사", "",
                     f"- 로컬 v1 raw/staging/masked {len(duplicates['local_files_scanned'])}개 파일, 발화 버전 {duplicates['unique_local_utterance_versions']}개와 비교했습니다.",
                     f"- 파일럿 내 완전 동일 발화 그룹: {len(duplicates['pilot_exact_utterance_groups'])}; 정규화 동일 그룹: {len(duplicates['pilot_normalized_utterance_groups'])}.",
                     f"- 파일럿 내 대화 유사도 0.90 이상: {len(duplicates['pilot_similar_conversations'])}; 로컬 v1 동일 발화 후보: {len(duplicates['local_v1_utterance_matches'])}; 로컬 v1 유사 대화 후보: {len(duplicates['local_v1_similar_conversations'])}.",
                     "- 중복 후보는 삭제하지 않았습니다. 로컬에 없는 v1 자료 및 의미적 중복은 검증 범위 밖입니다. 정규화·유사도 방식과 후보 위치는 duplicate_report.json에 있습니다.", "",
                     "## 재실행", "", "저장소 루트에서 실행합니다. 이 환경에는 Python이 PATH에 없어서 검증에 사용한 런타임 경로를 명시했습니다. 다른 환경에서는 Python 3.10+ 경로로 바꾸면 됩니다.", "", "```powershell",
                     python_command + " dataset/scripts/restore_pilot.py --check-only",
                     python_command + " -m unittest discover -s tests -p test_restore_pilot.py -v", "```", "",
                     "`--check-only`는 정본을 덮어쓰지 않고 TXT와 비교하며 보고서만 갱신합니다. 최초 복원은 옵션 없이 실행합니다. `--original-dir`로 원본 ZIP 해제 폴더를 지정하면 복사본과 원본도 비교합니다.", ""]
        (REPORTS / "README.md").write_text("\n".join(markdown), encoding="utf-8")
        print(json.dumps({"status": report["status"], "counts": counts,
                          "canonical": str(path.relative_to(ROOT)), "sha256": sha(data),
                          "review_notes": len(report["warnings"])}, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
