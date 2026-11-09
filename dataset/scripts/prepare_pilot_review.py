#!/usr/bin/env python3
"""Prepare/validate a two-reviewer CSV; never change the canonical JSONL.

Existing review inputs are preserved: an existing CSV is validated, not rebuilt.
Only the Python standard library is required.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CANONICAL = ROOT / "dataset/04. processed/v2_pilot/pilot_canonical.jsonl"
DIRECTORY = ROOT / "dataset/review/v2_pilot"
CSV_PATH = DIRECTORY / "human_review.csv"
EXPECTED_SHA = "847504a7178a1a0213b7855ebf9fe29aae9bbac51a04bd90abcd8aeb7c9281cd"
REVIEWERS = ("김해린", "임정윤")
RESULTS = {"미승인", "승인", "수정요청", "보류"}
SOURCE_COLUMNS = [
    "대화_ID", "발화_ID", "발화_번호", "화자", "대화_요약", "발화_내용",
    "피싱_여부", "위험_유형", "라벨_근거", "검토_필요", "검토_사유",
    "검수자_1", "검수자_2", "학습_반영",
]
EDIT_COLUMNS = [name for reviewer in REVIEWERS for name in
                (f"검수_결과_{reviewer}", f"수정_의견_{reviewer}", f"검수_일시_{reviewer}")]
EDIT_COLUMNS += ["최종_합의_결과", "합의_수정안", "최종_합의_일시"]
COLUMNS = SOURCE_COLUMNS[:11] + ["검수자_1"] + EDIT_COLUMNS[:3] + ["검수자_2"] + EDIT_COLUMNS[3:6] + EDIT_COLUMNS[6:] + ["학습_반영"]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def notes(number, uid):
    reasons = []
    if number == 5 and uid == 7:
        reasons.append("앱을 열어 주문 상태를 확인하라는 요구에 app_installation의 실행 유도 정의를 적용할지 검수. 3번 설치 요구 및 5번 정상 발화와 구분.")
    if number == 6:
        reasons.append("사내 인사팀 사칭이라는 합성 시나리오 전제가 본문과 일치하는지 대화 전체에서 확인.")
        if uid == 4:
            reasons.append("급여 정산 상담에서 '같이 듣자'는 응답의 문맥 연결 확인. 0003-4와 동일 문장이고 최신 revision_history의 변경 목록에 4번이 누락됨.")
        if uid == 6:
            reasons.append("최신 revision_history의 변경 목록에 6번이 누락됨. 4~7번 대화 연결 확인.")
        if uid == 7:
            reasons.append("설명표는 정상으로 바꿨다고 하나 최신 JSON은 비밀 유지 요구와 true/[secrecy]를 유지. 본문 기준 판정을 사람 합의로 결정.")
    if number == 7:
        reasons.append("가상 회원 서비스 조직 사칭을 institution_impersonation으로 볼지, 신청하지 않은 포인트 복구라는 기만 맥락이 충분한지 전체 대화에서 확인.")
        if uid == 5:
            reasons.append("최신 JSON의 5번 변경이 revision_history 변경 목록에 누락됨. 개인정보 요구와 라벨 근거 확인.")
    if number == 9 and uid == 5:
        reasons.append("loan_fraud와 money_transfer 멀티라벨 확인. 현재 발화의 대출 미끼 조건 및 보증금 이체 요구를 각각 판단하고 직전 발화 라벨을 자동 상속하지 않았는지 확인.")
    if number == 10 and uid == 5:
        reasons.append("미납액 결제의 money_transfer 및 기한 압박의 threat_pressure를 각각 검수. 정상 공공요금 안내와 구분되는 사칭·기만 전제를 전체 대화에서 확인.")
    if number == 11:
        reasons.append("온결기기지원의 가상 통신 지원 조직 사칭 설정과 본문 소속 표현 일치 여부 확인. 3번 이용 통신사·5번 명의 여부는 information_probing인지 정확한 개인정보 수집과 구분해 검수.")
    if number == 15 and uid == 7:
        reasons.append("최신 JSON의 7번 변경이 revision_history 변경 목록에 누락됨. 가상 주소 변경 절차의 상담 흐름 확인.")
    if number == 3 and uid == 4:
        reasons.append("0006-4와 동일 문장인 중복 후보. 두 대화의 서로 다른 문맥에서 자연스러운지 확인.")
    return " ".join(reasons)


def expected_rows():
    data = CANONICAL.read_bytes()
    require(digest(data) == EXPECTED_SHA, "Canonical SHA-256 changed; review baseline must be reconsidered")
    conversations = [json.loads(line) for line in data.decode("utf-8").splitlines()]
    require(len(conversations) == 16, "Expected 16 conversations")
    rows = []
    for number, conversation in enumerate(conversations, 1):
        require(conversation["synthetic_id"] == f"SYN2-TRAIN-{number:04}", "Conversation IDs/order mismatch")
        for utterance in conversation["utterances"]:
            uid = utterance["utterance_id"]
            reason = notes(number, uid)
            row = {
                "대화_ID": conversation["synthetic_id"],
                "발화_ID": f"{conversation['synthetic_id']}-{uid}",
                "발화_번호": str(uid), "화자": utterance["speaker"],
                "대화_요약": conversation["scenario_summary"],
                "발화_내용": utterance["text"],
                "피싱_여부": "true" if utterance["is_phishing"] else "false",
                "위험_유형": json.dumps(utterance["labels"], ensure_ascii=False),
                "라벨_근거": utterance["label_rationale"],
                "검토_필요": "예" if reason else "일반검수",
                "검토_사유": reason, "검수자_1": REVIEWERS[0], "검수자_2": REVIEWERS[1],
                "학습_반영": "미반영",
            }
            for reviewer in REVIEWERS:
                row[f"검수_결과_{reviewer}"] = "미승인"
                row[f"수정_의견_{reviewer}"] = ""
                row[f"검수_일시_{reviewer}"] = ""
            row.update(최종_합의_결과="미승인", 합의_수정안="", 최종_합의_일시="")
            rows.append(row)
    require(len(rows) == 136, "Expected 136 utterances")
    return rows


def validate(path, expected):
    data = path.read_bytes()
    require(data.startswith(b"\xef\xbb\xbf"), "Expected UTF-8 BOM for Korean Excel CSV")
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        require(reader.fieldnames == COLUMNS, "CSV column mismatch")
        rows = list(reader)
    require(len(rows) == 136, "CSV must contain exactly 136 utterances")
    baseline = {row["발화_ID"]: row for row in expected}
    require(len({row.get("발화_ID") for row in rows}) == 136, "Duplicate/missing utterance IDs")
    require({row["발화_ID"] for row in rows} == set(baseline), "CSV source ID mismatch")
    for row in rows:
        uid = row["발화_ID"]
        require(set(row) == set(COLUMNS) and all(value is not None for value in row.values()), f"Malformed row: {uid}")
        require(all(row[key] == baseline[uid][key] for key in SOURCE_COLUMNS), f"Source/annotation column changed: {uid}")
        for reviewer in REVIEWERS:
            result = row[f"검수_결과_{reviewer}"]
            require(result in RESULTS, f"Invalid reviewer result: {uid}/{reviewer}")
            if result != "미승인":
                require(row[f"검수_일시_{reviewer}"].strip(), f"Review date required: {uid}/{reviewer}")
            if result in {"수정요청", "보류"}:
                require(row[f"수정_의견_{reviewer}"].strip(), f"Review comment required: {uid}/{reviewer}")
        require(row["최종_합의_결과"] in RESULTS, f"Invalid final result: {uid}")
        if row["최종_합의_결과"] == "승인":
            require(all(row[f"검수_결과_{reviewer}"] == "승인" for reviewer in REVIEWERS), f"Both reviewers must approve: {uid}")
            require(row["최종_합의_일시"].strip(), f"Final agreement date required: {uid}")
    return {
        "status": "PASS", "rows": len(rows), "conversations": len({row["대화_ID"] for row in rows}),
        "source_phishing": sum(row["피싱_여부"] == "true" for row in rows),
        "source_normal": sum(row["피싱_여부"] == "false" for row in rows),
        "source_positive_labels": sum(len(json.loads(row["위험_유형"])) for row in rows),
        "priority_rows": sum(row["검토_필요"] == "예" for row in rows),
        "reviewer_results": {name: dict(Counter(row[f"검수_결과_{name}"] for row in rows)) for name in REVIEWERS},
        "final_results": dict(Counter(row["최종_합의_결과"] for row in rows)),
        "canonical_sha256": EXPECTED_SHA, "csv_sha256": digest(data),
        "canonical_unchanged": digest(CANONICAL.read_bytes()) == EXPECTED_SHA,
        "training_applied": False,
        "note": "CSV has no formulas or automatic approval/integration. This validator never applies data to training.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    try:
        expected = expected_rows()
        created = False
        if not CSV_PATH.exists() and not args.check_only:
            DIRECTORY.mkdir(parents=True, exist_ok=True)
            with CSV_PATH.open("x", encoding="utf-8-sig", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=COLUMNS)
                writer.writeheader()
                writer.writerows(expected)
            created = True
        report = validate(CSV_PATH, expected)
        require(report["canonical_unchanged"], "Canonical was modified")
        report["csv_created_this_run"] = created
        report_path = ROOT / "reports/v2_pilot/human_review_validation.json"
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"FAIL: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
