#!/usr/bin/env python3
"""Audit recorded human decisions and export approved, complete conversations.

Never interprets free-text amendments as an approved new label. Never trains,
changes a split, edits source files, or modifies existing training code.
"""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

import prepare_pilot_review as review
import restore_pilot as source

ROOT = review.ROOT
TOKENS = {"PERSON", "PHONE_NUMBER", "ACCOUNT_NUMBER", "CARD_NUMBER", "ADDRESS", "RRN", "BIRTH", "EMAIL", "PW"}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"".join((json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8") for row in rows))


def analyze(rows, baseline):
    expected = {row["발화_ID"]: row for row in baseline}
    seen = Counter(row.get("발화_ID") for row in rows)
    errors, issues, accepted, changes = [], [], set(), []
    missing_ids = sorted(set(expected) - seen.keys())
    unexpected_ids = sorted(seen.keys() - expected.keys(), key=str)
    duplicates = sorted(key for key, count in seen.items() if count > 1)
    if missing_ids or unexpected_ids or duplicates:
        errors.append({"code": "ID_COVERAGE", "missing": missing_ids, "unexpected": unexpected_ids, "duplicates": duplicates})
    counts = Counter()
    for row in rows:
        uid = row.get("발화_ID", "")
        reasons = []
        if set(row) != set(review.COLUMNS) or any(value is None for value in row.values()):
            reasons.append("CSV_ROW_SHAPE")
        statuses = [row.get(f"검수_결과_{name}", "") for name in review.REVIEWERS]
        counts["both_approved"] += all(value == "승인" for value in statuses)
        counts["one_approved"] += sum(value == "승인" for value in statuses) == 1
        counts["change_requested"] += "수정요청" in statuses or row.get("최종_합의_결과") == "수정요청"
        counts["held"] += "보류" in statuses or row.get("최종_합의_결과") == "보류"
        counts["disagreement"] += len(set(statuses)) > 1
        counts["change_hold_or_disagreement"] += (
            "수정요청" in statuses or "보류" in statuses or len(set(statuses)) > 1 or
            row.get("최종_합의_결과") in {"수정요청", "보류"}
        )
        counts["review_incomplete"] += any(value in {"", "미승인"} for value in statuses)
        counts["empty_result_cells"] += sum(not value for value in statuses)
        for name, status in zip(review.REVIEWERS, statuses):
            date = row.get(f"검수_일시_{name}", "")
            comment = row.get(f"수정_의견_{name}", "")
            counts["blank_reviewer_dates"] += not bool(date.strip())
            if status not in review.RESULTS:
                reasons.append(f"INVALID_RESULT:{name}")
            if status in {"", "미승인"}:
                reasons.append(f"REVIEW_NOT_RECORDED:{name}")
            if status in review.RESULTS - {"미승인"} and not date.strip():
                reasons.append(f"REQUIRED_DATE_MISSING:{name}")
                counts["conditional_required_missing_cells"] += 1
            if status in {"수정요청", "보류"} and not comment.strip():
                reasons.append(f"REQUIRED_COMMENT_MISSING:{name}")
                counts["conditional_required_missing_cells"] += 1
        final = row.get("최종_합의_결과", "")
        if final not in review.RESULTS:
            reasons.append("INVALID_FINAL_RESULT")
        if final != "승인":
            reasons.append("FINAL_NOT_APPROVED")
        final_date = row.get("최종_합의_일시", "")
        counts["blank_final_dates"] += not bool(final_date.strip())
        if final == "승인" and not final_date.strip():
            reasons.append("FINAL_DATE_MISSING")
            counts["conditional_required_missing_cells"] += 1
        comments = {name: row.get(f"수정_의견_{name}", "") for name in review.REVIEWERS}
        amendment = row.get("합의_수정안", "")
        combined = " ".join([*comments.values(), amendment])
        has_comments = bool(combined.strip())
        counts["comment_rows"] += has_comments
        # A hint is reported as a proposal, never parsed/applied as a decision.
        label_hint = bool(re.search(r"라벨|위험.?유형|피싱.?여부|labels|is_phishing|" + "|".join(source.LABELS), combined, re.I))
        counts["label_proposal_rows"] += label_hint
        if has_comments:
            reasons.append("FREE_TEXT_REQUIRES_EXPLICIT_RESOLUTION")
        if uid not in expected or seen[uid] != 1:
            reasons.append("UNKNOWN_OR_DUPLICATE_ID")
        elif any(row.get(key) != expected[uid][key] for key in review.SOURCE_COLUMNS):
            reasons.append("SOURCE_COLUMNS_CHANGED")
        if not all(value == "승인" for value in statuses):
            reasons.append("BOTH_APPROVALS_REQUIRED")
        if not reasons:
            accepted.add(uid)
            changes.append({"utterance_id": uid, "original_is_phishing": expected[uid]["피싱_여부"],
                            "approved_is_phishing": expected[uid]["피싱_여부"],
                            "original_labels": json.loads(expected[uid]["위험_유형"]),
                            "approved_labels": json.loads(expected[uid]["위험_유형"]), "changed_fields": [],
                            "reason": "Both reviewers and final agreement explicitly approve unchanged canonical content."})
        else:
            issues.append({"utterance_id": uid, "conversation_id": row.get("대화_ID"),
                           "reasons": reasons, "reviewer_results": dict(zip(review.REVIEWERS, statuses)),
                           "comments": comments, "final_result": final, "agreed_amendment": amendment,
                           "label_change_proposal_hint": label_hint})
    # Coverage/shape failures must not produce any approved output.
    if errors:
        accepted.clear()
        changes.clear()
    keys = ("both_approved", "one_approved", "change_requested", "held", "disagreement", "change_hold_or_disagreement", "review_incomplete",
            "empty_result_cells", "blank_reviewer_dates", "blank_final_dates", "conditional_required_missing_cells",
            "comment_rows", "label_proposal_rows")
    return {key: counts[key] for key in keys}, accepted, issues, errors, changes


def select_conversations(conversations, accepted):
    candidates, usable, contexts, windows = [], [], [], []
    for original in conversations:
        cid = original["synthetic_id"]
        ids = [f"{cid}-{u['utterance_id']}" for u in original["utterances"]]
        approved = [uid for uid in ids if uid in accepted]
        excluded = [uid for uid in ids if uid not in accepted]
        at_risk = []
        for index, uid in enumerate(ids):
            if uid in accepted:
                previous = ids[max(0, index - 5):index]
                denied = [key for key in previous if key not in accepted]
                if denied:
                    at_risk.append({"target": uid, "excluded_previous_ids": denied})
                if not excluded:
                    windows.append({"target": uid, "previous_utterance_ids": previous, "split": "train"})
        if approved:
            candidate = copy.deepcopy(original)
            candidate["utterances"] = [u for u in candidate["utterances"] if f"{cid}-{u['utterance_id']}" in accepted]
            candidates.append(candidate)
        if not excluded:
            usable.append(copy.deepcopy(original))
        contexts.append({"conversation_id": cid, "source_utterances": len(ids), "approved_ids": approved,
                         "excluded_ids": excluded, "targets_with_excluded_previous_context": at_risk,
                         "usable": not excluded,
                         "decision": "complete_approved_conversation" if not excluded else "exclude_conversation_to_preserve_context"})
    return candidates, usable, contexts, windows


def mask_scan(conversations):
    invalid, candidates = [], []
    patterns = {"phone": r"(?<!\d)(?:01[016789]|02|0[3-6][1-5])[- ]?\d{3,4}[- ]?\d{4}(?!\d)",
                "rrn": r"(?<!\d)\d{6}[- ]?[1-4]\d{6}(?!\d)",
                "email": r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}"}
    for conversation in conversations:
        for u in conversation["utterances"]:
            uid = f"{conversation['synthetic_id']}-{u['utterance_id']}"
            for token in re.findall(r"\[([^\[\]]+)\]", u["text"]):
                if token not in TOKENS:
                    invalid.append({"id": uid, "token": token})
            for kind, pattern in patterns.items():
                if re.search(pattern, u["text"]):
                    candidates.append({"id": uid, "kind": kind})
    return {"invalid_tokens": invalid, "unmasked_pattern_candidates": candidates,
            "limitation": "Pattern screening does not prove that names, addresses or account/card identifiers are absent. Human masking review remains required."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-csv", type=Path, default=review.CSV_PATH)
    args = parser.parse_args()
    protected = [review.CANONICAL, args.review_csv, review.DIRECTORY / "README.md",
                 ROOT / "reports/v2_pilot/restoration_manifest.json"]
    before = {str(path): sha(path.read_bytes()) for path in protected}
    canonical = [source.parse_json(line) for line in review.CANONICAL.read_text(encoding="utf-8").splitlines()]
    restored, _ = source.restore()
    source.validate(canonical, restored)
    baseline = review.expected_rows()
    with args.review_csv.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        source.require(reader.fieldnames == review.COLUMNS, "Actual review CSV headers differ from the documented schema")
        rows = list(reader)
    counts, accepted, issues, errors, changes = analyze(rows, baseline)
    candidates, usable, context, windows = select_conversations(canonical, accepted)
    tag = "approval_" + before[str(args.review_csv)][:12]
    report_dir = ROOT / "reports/v2_pilot" / tag
    data_dir = ROOT / "dataset/04. processed/v2_pilot" / tag
    write_jsonl(data_dir / "pilot_approved.jsonl", usable)
    write_jsonl(data_dir / "pilot_double_approved_candidates.jsonl", candidates)
    write_jsonl(report_dir / "unresolved_items.jsonl", issues)
    write_jsonl(report_dir / "label_change_audit.jsonl", changes)
    write_jsonl(report_dir / "context_windows.jsonl", windows)
    write_json(report_dir / "conversation_context_audit.json", context)
    reference = source.duplicate_report(canonical)
    write_json(report_dir / "local_reference_duplicate_scan.json", reference)
    source_mask = mask_scan(canonical)
    approved_mask = mask_scan(usable)
    label_counts = {label: 0 for label in source.LABELS}
    approved_utterances = [u for c in usable for u in c["utterances"]]
    for u in approved_utterances:
        for label in u["labels"]:
            label_counts[label] += 1
    for conversation in usable:
        source.require(conversation["split"] == "train" and conversation["is_synthetic"] is True, "Synthetic train invariants")
        source.require(all(f"{conversation['synthetic_id']}-{u['utterance_id']}" in accepted for u in conversation["utterances"]), "Unapproved target exported")
    source.require(all(all(uid in accepted for uid in window["previous_utterance_ids"]) for window in windows), "Unapproved context exported")
    exported_data = (data_dir / "pilot_approved.jsonl").read_bytes()
    parsed_export = [source.parse_json(line) for line in exported_data.decode("utf-8").splitlines()]
    source.require(parsed_export == usable, "Export roundtrip mismatch")
    ready = False  # Existing loader/split manifest are not available for compatibility verification.
    summary = {"review_csv_rows": len(rows), "recorded_completed_reviews": len(rows) - counts["review_incomplete"],
               **counts, "eligible_approved_utterances": len(accepted), "final_exported_utterances": len(approved_utterances),
               "usable_conversations": len(usable), "excluded_conversations": len(context) - len(usable),
               "approved_phishing": sum(u["is_phishing"] for u in approved_utterances),
               "approved_normal": sum(not u["is_phishing"] for u in approved_utterances),
               "positive_labels": label_counts, "approved_label_changes_applied": 0,
               "training_ready": ready, "input_hashes": before,
               "approval_policy": "Two explicit approvals, final explicit approval, all dates, unchanged source, no unresolved free-text amendments. Partial conversations are held in a separate candidate file and excluded from final export.",
               "training_performed": False, "git_push_performed": False, "pr_created": False}
    write_json(report_dir / "review_summary.json", summary)
    validation = {
        "status": "NOT_READY", "empty_export_is_not_training_ready": not bool(approved_utterances),
        "blockers": (["Specified CSV has no eligible recorded approvals"] if not accepted else []) +
                    ["Existing KoELECTRA loader, label2id/tokenizer configuration and actual v1 train/validation/test split manifest are unavailable"],
        "input_coverage_errors": errors, "source_schema_and_evidence": "PASS",
        "source_masking_screen": source_mask,
        "approved_schema_ids_and_labels": "NOT_RUN_EMPTY_EXPORT" if not usable else "PASS_SOURCE_SUBSET_AND_ROUNDTRIP",
        "approved_masking_screen": {"status": "NOT_RUN_EMPTY_EXPORT" if not usable else "SCREENED", **approved_mask},
        "approved_internal_duplicates": "NOT_RUN_EMPTY_EXPORT" if not usable else "SEE_LOCAL_REFERENCE_SCAN_AND_RESTRICT_TO_EXPORTED_IDS",
        "local_v1_reference_scan": {"status": "REFERENCE_ONLY_NOT_ACTUAL_TRAIN_SPLIT", "files": len(reference["local_files_scanned"]),
                                    "canonical_utterance_matches": len(reference["local_v1_utterance_matches"]),
                                    "canonical_similar_conversations": len(reference["local_v1_similar_conversations"])},
        "actual_v1_training_duplicate_check": "NOT_VERIFIED_ACTUAL_TRAIN_DATA_PATH_REQUIRED",
        "family_split_check": {"local_canonical": "16 unique families, all train",
                               "global_train_validation_test": "NOT_VERIFIED_SPLIT_MANIFEST_REQUIRED"},
        "context_check": {"exported_windows": len(windows), "unapproved_ids_in_export": 0,
                          "status": "NO_EXAMPLES_EXPORTED" if not windows else "PASS_APPROVED_ONLY",
                          "max_previous_utterances": 5, "loader_behavior_verified": False,
                          "partial_conversation_policy": "exclude entire conversation from final export"},
        "compatibility": "UNVERIFIED_NO_TRAINING_CODE; nested synthetic_id/utterances differs from observed flat v1 records",
        "approved_jsonl_sha256": sha(exported_data), "approved_jsonl_bytes": len(exported_data),
        "source_files_unchanged": all(sha(Path(path).read_bytes()) == value for path, value in before.items()),
    }
    source.require(validation["source_files_unchanged"], "Protected source changed during audit")
    write_json(report_dir / "validation_report.json", validation)
    md = ["# 사람 검수 결과와 승인 데이터 점검", "",
          "지정 CSV의 실제 값에 근거한 결과입니다. 현재 파일은 검수 완료본이 아니라 두 검수자와 최종 합의가 모두 미승인인 초기 검수표입니다." if counts["review_incomplete"] == len(rows) else "CSV의 명시적 승인과 검수 규칙을 기준으로 추출했습니다.", "",
          "| 항목 | 결과 |", "|---|---|",
          f"| 전체 검수 발화 | {len(rows)}행; 양쪽 결과 입력 완료 {summary['recorded_completed_reviews']}행 |",
          f"| 두 사람 모두 승인 / 한 사람만 승인 | {counts['both_approved']} / {counts['one_approved']} |",
          f"| 최종 승인 발화 | {len(approved_utterances)} (승인 조건 충족 후보 {len(accepted)}) |",
          f"| 수정·보류·불일치 | 수정요청 {counts['change_requested']}, 보류 {counts['held']}, 결과 불일치 {counts['disagreement']} |",
          f"| 검수 미기록 | {counts['review_incomplete']}행 |",
          f"| 라벨 변경 제안 | {counts['label_proposal_rows']}행; 자유문 의견은 자동 변경하지 않음 |",
          f"| 승인된 피싱/정상 발화 | {summary['approved_phishing']} / {summary['approved_normal']} |",
          "| 유형별 Positive 수 | " + ", ".join(f"{key}={value}" for key, value in label_counts.items()) + " |",
          f"| 사용 가능한 대화 수 | {len(usable)} / 16 |",
          "| 기존 v1 데이터 중복 검사 | 로컬 참고 자료와 정본 비교만 수행; 실제 v1 학습 분할 데이터 검사는 미완료 |",
          "| 학습 준비 상태 | 미준비. 승인 완료 CSV와 실제 v1 입력/분할 자료 필요 |", "",
          f"결과값 공란 {counts['empty_result_cells']}칸, 검수자 일시 공란 {counts['blank_reviewer_dates']}칸, 최종 합의 일시 공란 {counts['blank_final_dates']}칸입니다. 입력된 결과 상태에 따른 필수 일시/의견 누락은 {counts['conditional_required_missing_cells']}칸입니다. 미승인은 완료된 검수로 세지 않았습니다.", "",
          "## 승인·수정 처리", "",
          "검수표의 실제 결과 열은 `검수_결과_김해린`, `검수_결과_임정윤`, `최종_합의_결과`이며 일시 열도 각각 확인했습니다. README의 승인 규칙을 적용했습니다. 양쪽 승인만으로는 최종 합의와 일시를 생략하지 않습니다.",
          "수정 의견·합의 수정안은 원문 그대로 unresolved_items.jsonl에 보존합니다. 자유문이 남아 있으면 임의로 해결됐다고 가정하지 않습니다. 라벨 변경 제안 탐지는 명시적 키워드에 따른 후보 집계이며 사람이 승인한 구조화된 수정본을 대신하지 않습니다.",
          "현재 최종 라벨은 승인된 원본 그대로만 추출할 수 있습니다. 승인된 구조화 수정본이 없어 라벨 변경 적용은 0건입니다. label_change_audit.jsonl은 승인된 원본/최종 라벨 비교 기록이며 승인 데이터가 없으면 0행입니다.", "",
          "## 문맥과 형식", "",
          "이전 최대 5발화라는 사용자 요구를 기준으로 ID 문맥 창을 점검했습니다. 제외된 발화를 건너뛰어 문맥을 새로 연결하거나 발화 번호를 다시 매기지 않습니다. 일부만 승인된 대화는 후보 파일에만 보관하고 최종 파일에서는 대화 전체를 제외합니다.",
          "현재 승인 출력은 0행·0바이트입니다. JSONL 형식상 빈 파일을 만들었지만 학습에 사용할 데이터가 생겼다는 뜻은 아닙니다. 승인 데이터 대상 형식·마스킹·중복 검사는 빈 집합이므로 통과했다고 보고하지 않았습니다.",
          "생성/수정 이력, source_kind, actual_call, 시나리오 가족, 원본 split=train 및 is_synthetic=true는 추출 시 그대로 보존합니다. 데이터 출처 및 검수 파일 해시는 review_summary.json에 있습니다. 원본 review_status를 AI가 변경하지 않습니다.", "",
          "## 중복·마스킹·분할 검증 범위", "",
          f"정본 136발화를 로컬 raw/staging/masked {len(reference['local_files_scanned'])}개 파일과 비교한 참고 진단을 local_reference_duplicate_scan.json에 저장했습니다. 로컬 v1 동일 발화 후보 {len(reference['local_v1_utterance_matches'])}개, 유사 대화 후보 {len(reference['local_v1_similar_conversations'])}개입니다. 이것은 실제 v1 학습 데이터의 사용 여부나 중복 검증 완료를 뜻하지 않습니다.",
          f"정본 내부 동일 문장 그룹 {len(reference['pilot_exact_utterance_groups'])}개(0003-4와 0006-4), 유사 대화 후보 {len(reference['pilot_similar_conversations'])}개입니다. 중복 후보는 삭제하지 않았습니다.",
          f"정본 허용 외 마스킹 토큰 {len(source_mask['invalid_tokens'])}개, 전화·주민번호·이메일 패턴 후보 {len(source_mask['unmasked_pattern_candidates'])}개입니다. 이름·주소·계좌번호를 포함한 개인정보 부재를 이 패턴 검사만으로 보증하지 않습니다.",
          "정본의 16개 가족은 서로 다르고 전부 train입니다. 실제 v1/v2 전체 train/validation/test 분할 목록이 없으므로 전체 가족 분할 충돌 검증은 미완료입니다. 어떤 자료도 validation/test로 재분류하지 않았습니다.", "",
          "## 기존 KoELECTRA 입력과 변환 계획", "",
          "현재 `risk_speech_ai/`와 `dataset/processed/`에는 학습 코드/입력이 없습니다. 실제 v1 원자료는 `dataset/01. raw/`에 있고 가공 참고자료는 `dataset/02. staging/`, `dataset/03. masked/`에 있으나 실제 학습 split을 식별할 자료는 없습니다.",
          "필요한 경로: 실제 v1 train·validation·test 파일 또는 split manifest, 기존 KoELECTRA Dataset/입력 생성기·collator 코드, label2id와 tokenizer/max_length 설정 파일. 현재 존재하지 않는 파일 이름을 실제 경로처럼 가정하지 않았습니다.",
          "관찰한 v1 가공 자료는 발화 단위 conversation_id/utterance_id/text/is_phishing/labels 구조이며 파일럿은 대화 단위 synthetic_id/utterances 구조입니다. 로더 호환성은 미확인입니다. 기존 PN ID 정규식에는 SYN2 ID가 맞지 않으므로 별도 어댑터에서 원래 synthetic_id를 유지하는 매핑이 필요합니다.",
          "변환 순서: (1) 실제 로더 스키마·라벨 순서·문맥 직렬화 규칙 확인, (2) 별도 어댑터에서 승인된 완전 대화만 발화 단위로 펼치고 출처·이력은 메타데이터로 동반 보존, (3) 원래 순서의 이전 최대 5개 승인 발화와 타깃만 결합, (4) 제외 ID 유입 0건·라벨 벡터·토크나이저 길이 검증, (5) 실제 v1 분할과 중복/가족 충돌 검사. 기존 학습 코드와 체크포인트는 수정하지 않습니다.", "",
          "## 결과물", "",
          f"- 승인 데이터: `{(data_dir / 'pilot_approved.jsonl').relative_to(ROOT).as_posix()}`",
          "- 양쪽 승인 후보: 같은 데이터 폴더의 pilot_double_approved_candidates.jsonl (최종 문맥 심사 전)",
          "- 집계: review_summary.json / 이 문서", "- 미해결·불일치·검수 미기록: unresolved_items.jsonl",
          "- 라벨 전후 비교: label_change_audit.jsonl", "- 검증: validation_report.json",
          "- 대화 사용 판단 및 문맥: conversation_context_audit.json, context_windows.jsonl", "",
          "검수 완료본 경로를 확인한 뒤 재집계: `python dataset/scripts/finalize_pilot_review.py --review-csv <검수완료_CSV_경로>`. 이 환경은 Python이 PATH에 없으므로 이전 검수 안내문의 Python 실행 파일 경로를 사용합니다. 입력 CSV 해시별로 결과 폴더를 분리하여 이전 감사 결과를 보존합니다.", "",
          "정본·검수 CSV·검수 README·기존 복원 이력은 SHA-256으로 보존을 확인했습니다. 학습 데이터에 병합하지 않았으며 학습·Git push·PR 생성은 수행하지 않았습니다.", ""]
    (report_dir / "review_summary.md").write_text("\n".join(md), encoding="utf-8")
    print(json.dumps({"status": "NOT_READY", "review_rows": len(rows), **counts,
                      "approved_export_utterances": len(approved_utterances), "usable_conversations": len(usable),
                      "reports": str(report_dir.relative_to(ROOT)), "approved": str((data_dir / "pilot_approved.jsonl").relative_to(ROOT)),
                      "protected_files_unchanged": validation["source_files_unchanged"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
