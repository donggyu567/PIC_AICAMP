"""Write review suggestions and source asset inventory; never edit canonical CSVs."""
import csv
import json
from collections import defaultdict
from pathlib import Path

from audit_v2_pipeline import ROOT, OUT, REF, TRAIN, VALIDATION, RECOVERED, read_json, read_jsonl, sha


def write_csv(name, rows, columns):
    with (OUT/name).open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def main():
    train, val = read_jsonl(TRAIN), read_jsonl(VALIDATION)
    conversations = {c["synthetic_id"]: c for c in train+val}
    indexed = {f"{c['synthetic_id']}-{u['utterance_id']}": (c, u) for c in train+val for u in c["utterances"]}
    pending = {}
    def add(key, category, reason, proposal, priority="중점"):
        c, u = indexed[key]
        row = pending.setdefault(key, dict(id=key, split=c["split"], conversation_id=c["synthetic_id"], utterance_id=u["utterance_id"],
            speaker=u["speaker"], original_text=u["text"], original_is_phishing=u["is_phishing"], original_labels=u["labels"],
            original_rationale=u["label_rationale"], priority=priority, categories=[], reasons=[], proposals=[],
            previous_utterances=[dict(id=h["utterance_id"], text=h["text"]) for h in c["utterances"][max(0,u["utterance_id"]-6):u["utterance_id"]-1]],
            review_status="needs_human_review", human_approval_assigned=False))
        row["categories"].append(category)
        row["reasons"].append(reason)
        row["proposals"].append(proposal)
        if priority == "우선":
            row["priority"] = priority
    normal_focus = {
        "SYN2-TRAIN-0021": "지점 주화 교환 및 예약용 이름·연락처는 정상 고객 발신 문맥에서 최소 수집이다.",
        "SYN2-TRAIN-0022": "정상 병원 문서 조회의 성명·생년월일 확인과 대리수령 서면 동의를 부적절한 개인정보 수집으로 오인하지 않는다.",
        "SYN2-TRAIN-0023": "사전 공지된 훈련의 장비 구역 출입 통제는 사기성 처벌·손실 압박과 다르다.",
        "SYN2-TRAIN-0024": "파일·비밀번호를 상담원에게 말하지 말라는 보호 안내는 통화 사실을 제3자에게 숨기라는 요구가 아니다.",
        "SYN2-VALIDATION-0017": "고객이 요청한 카드 차단은 사기성 계좌 동결 협박이 아니다.",
        "SYN2-VALIDATION-0018": "정상 착불 요금 결제와 수취 거절 선택은 사기성 금전 이전이 아니다.",
        "SYN2-VALIDATION-0019": "정상 반품 배송비 공제와 외부 송금 요구의 인용은 사기성 송금 명령이 아니다.",
        "SYN2-VALIDATION-0020": "조건부 금리·심사·부결 가능성을 설명하는 정상 대출과 무조건 승인을 구분한다.",
        "SYN2-VALIDATION-0021": "고객 발신 숙박 예약 조회의 이름·이메일 확인은 최소한의 적법한 조회로 설정되어 있다.",
        "SYN2-VALIDATION-0022": "고객 요청·명시적 동의·즉시 종료 가능한 공식 원격지원에서 앱 실행이 정상으로 설정되어 있다.",
        "SYN2-VALIDATION-0023": "제3자 연락처·공동현관 비밀번호를 받지 않는 배송 인계는 개인정보 보호 안내다.",
        "SYN2-VALIDATION-0024": "상담 사실 공유는 허용하고 타인의 계좌정보만 공개하지 않는 정상 상담이다.",
    }
    for cid, focus in normal_focus.items():
        for u in conversations[cid]["utterances"]:
            add(f"{cid}-{u['utterance_id']}", "정상 상담 라벨 경계", focus,
                "현재 false/[]를 자동 승인하지 말고 고객 발신·정상 절차·최소 수집 전제를 전후 문맥과 함께 확인. 불일치가 있으면 구체적 원문과 변경안을 별도 검수 의견에 기록.")
    multi = {
        "SYN2-TRAIN-0017-7": "송금 명령과 기존 영업 담당자에 대한 은폐 요구가 현재 발화에 모두 직접 표현된다.",
        "SYN2-TRAIN-0019-6": "허위 대출·장학금 전환 보장과 학교 계정 비밀번호 수집이 한 발화에 함께 표현된다.",
        "SYN2-TRAIN-0020-9": "10분 시한·잔액 소멸 위협과 송금 명령이 함께 표현된다.",
    }
    for key, reason in multi.items():
        add(key, "신규 멀티라벨", reason, "각 라벨에 해당하는 구절을 따로 지정하고 직전 발화의 라벨 상속이 아닌지 확인. 한 행위가 성립하지 않는다고 판단하면 사람 합의로 해당 라벨만 수정 제안.", "우선")
    for u in conversations["SYN2-TRAIN-0020"]["utterances"]:
        add(f"SYN2-TRAIN-0020-{u['utterance_id']}", "선입금형 시나리오 유사성",
            "기존 TRAIN 0009 및 VALIDATION 0001과 금액을 먼저 보내야 이익·잔액을 얻는 상위 기제를 공유한다. 계정 복구 정보 수집과 투자 피해 회수의 재피해 전개가 별도 가족으로 충분한지 미확정이다.",
            "대화 전체의 사전 사건·유인·질문·지급 요구·피해자 대응 순서를 나란히 비교해 같은 가족 여부를 사람이 결정. 이번 작업에서는 문장·라벨·가족 ID를 바꾸지 않음.", "우선")
    for key in ("SYN2-TRAIN-0018-3", "SYN2-TRAIN-0018-5", "SYN2-TRAIN-0018-7", "SYN2-TRAIN-0018-9"):
        add(key, "떠보기와 정확정보 수집", "명의·이력 확인성 질문과 성명·생년월일·전체 주민번호 요구의 경계를 확인해야 한다.",
            "정확한 식별값을 직접 요구하면 personal_information, 후보·이력을 떠보면 information_probing이라는 현재 가이드를 각 구절에 적용.")
    for c in train[16:]+val:
        for u in c["utterances"]:
            if "institution_impersonation" in u["labels"] and not any(h["is_phishing"] for h in c["utterances"][:u["utterance_id"]-1]):
                add(f"{c['synthetic_id']}-{u['utterance_id']}", "실시간 문맥 가시성",
                    "사칭 설정은 전체 시나리오·뒤의 요구에서 드러나지만 현재 발화와 과거 최대 5개만으로는 정상 소속 소개와 구분하기 어려울 수 있다. 모델에는 시나리오 요약·미래 발화가 들어가지 않는다.",
                    "가이드의 전체 문맥 정답과 실시간 접두 문맥 예측 목적이 일치하는지 검토. 현재 라벨을 자동 반전하지 말고 판단 근거·식별 불가능성을 기록.")
    for key in ("SYN2-TRAIN-0003-4", "SYN2-TRAIN-0006-4"):
        add(key, "기존 TRAIN 동일 문장", "기존 16대화 내부의 동일 문장 1쌍이며 그대로 보존했다.", "동일 문장이 다른 문맥에 필요한지 확인하고 유지·수정 여부를 사람이 결정. 삭제 자동화 없음.")
    overlap = read_json(OUT/"independence_result.json")
    for row in overlap["v2_train_vs_actual_v1"]["candidates"]:
        add(row["left"], "실제 v1 입력 유사 문장",
            f"복구한 실제 v1의 {row['right']}와 유사도 {row['similarity']}; v1 원문: {row['right_text']}",
            "현재 후보는 신청 부인이라는 일반 피해자 반응의 표현 유사성이다. 대화 전체 재사용인지 단순 공통 표현인지 사람이 구분하고 기록; 원문 자동 수정 없음.", "우선")
    rows = sorted(pending.values(), key=lambda r:(r["split"],r["conversation_id"],r["utterance_id"]))
    (OUT/"human_review_cases.jsonl").write_text("".join(json.dumps(r,ensure_ascii=False)+"\n" for r in rows),encoding="utf-8")
    columns=["id","split","conversation_id","utterance_id","speaker","original_text","original_is_phishing","original_labels",
             "original_rationale","priority","categories","reasons","proposals","previous_utterances","review_status","human_approval_assigned"]
    flattened=[{k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in row.items()} for row in rows]
    write_csv("human_review_cases.csv",flattened,columns)
    pairs=[
        ("SYN2-TRAIN-0020","SYN2-TRAIN-0009","선입금 뒤 금전적 이익을 제공한다는 공통 기제. 신규는 투자 재피해·지갑 접근 수집이 결합됨."),
        ("SYN2-TRAIN-0020","SYN2-VALIDATION-0001","자산을 받으려면 먼저 지급하라는 공통 구조. 투자 회수와 거래 정산의 차이가 별도 가족으로 충분한지 확인."),
        ("SYN2-TRAIN-0001","SYN2-VALIDATION-0003","공식 문제 해결을 주장하며 별도 소프트웨어 실행을 요구. 은행 보안 앱과 PC 원격 세무 대조의 전개 차이를 확인."),
        ("SYN2-TRAIN-0001","SYN2-VALIDATION-0004","기존 서비스로는 해결이 안 된다고 별도 소프트웨어를 요구하는 상위 흐름을 공유. 앱명·기관명만 바꾼 전개인지 검토."),
        ("SYN2-TRAIN-0002","SYN2-VALIDATION-0012","설치 요구라는 공통 위험 행위가 대출 심사와 주주 의결권 위임에서 각각 반복. 역할·분기·거절 대응을 비교."),
        ("SYN2-TRAIN-0019","SYN2-VALIDATION-0007","허위 대출 혜택을 제시하는 공통 기제. 장학금 전환·학교 계정 탈취와 기기 구매·재판매금 현금화의 차이 확인."),
        ("SYN2-TRAIN-0019","SYN2-VALIDATION-0008","조건 없는 승인과 개인정보 요구가 공통. 가족 보증인 수집과 학교 계정 탈취를 구별하는 기준 확인."),
        ("SYN2-TRAIN-0022","SYN2-VALIDATION-0021","정상 고객 발신·최소 본인 확인 후 처리라는 흐름이 공통. 의료문서 수령과 숙박 예약 변경의 독립성 검토."),
        ("SYN2-TRAIN-0024","SYN2-VALIDATION-0022","정상 기기 지원·비밀번호를 받지 않는 안내가 공통. 로컬 반납 초기화와 동의 기반 원격지원의 다른 작업 흐름 확인."),
    ]
    pair_rows=[]
    for left,right,reason in pairs:
        a,b=conversations[left],conversations[right]
        pair_rows.append(dict(left_id=left,right_id=right,left_family=a["scenario_family_id"],right_family=b["scenario_family_id"],
            left_split=a["split"],right_split=b["split"],reason=reason,
            left_transcript="\n".join(f"{u['utterance_id']} {u['speaker']}: {u['text']}" for u in a["utterances"]),
            right_transcript="\n".join(f"{u['utterance_id']} {u['speaker']}: {u['text']}" for u in b["utterances"]),
            proposal="별개 가족 유지 여부를 독립적인 사람이 결정. 동일 전개라면 이후 별도 승인된 수정 작업에서 처리; 이번에는 변경하지 않음.",status="needs_human_review"))
    write_csv("semantic_scenario_pairs.csv",pair_rows,list(pair_rows[0]))
    v1texts=read_jsonl(RECOVERED/"tuned.jsonl")
    v1labels={(r["conversation_id"],r["utterance_id"]):r for r in read_jsonl(RECOVERED/"labels.jsonl")}
    grouped=defaultdict(list)
    for row in v1texts:grouped[row["conversation_id"]].append(row)
    index=[]
    for cid, items in sorted(grouped.items()):
        items.sort(key=lambda r:r["utterance_id"])
        index.append(dict(conversation_id=cid,utterances=len(items),
            labels=json.dumps(sorted({label for r in items for label in v1labels[cid,r["utterance_id"]]["labels"]}),ensure_ascii=False),
            transcript="\n".join(f"{r['utterance_id']}: {r['tuned_text']}" for r in items),
            semantic_family_status="NOT_AVAILABLE_IN_ORIGINAL_V1_INPUT"))
    write_csv("v1_conversation_review_index.csv",index,list(index[0]))
    repro=read_json(REF/"artifacts/risk_speech_ai/reports/reproducibility.json")
    recovery=read_json(OUT/"v1_input_recovery.json")
    assets=[]
    for name,row in recovery["output"].items():assets.append(dict(asset=f"actual_v1_{name}",status="READY_EXACT_HASH_RECOVERY",**row))
    for name in ("artifacts/risk_speech_ai/koelectra_risk_v1.pt","checkpoints/risk_speech_v1.pt"):
        assets.append(dict(asset="trained_v1_checkpoint",status="NOT_FOUND",expected_path=str(ROOT/name),actual_path=None,
            actual_sha256=None,expected_sha256=repro["checkpoint"]["sha256"],expected_bytes=repro["checkpoint"]["bytes"],load_status="BLOCKED_FILE_MISSING"))
    for path in sorted((REF/"risk_speech_ai").glob("*.py")):
        assets.append(dict(asset="PR35_source_code",status="READY_SOURCE_ONLY",path=str(path),bytes=path.stat().st_size,sha256=sha(path)))
    for path in sorted((REF/"artifacts/risk_speech_ai/reports").glob("*")):
        if path.is_file():assets.append(dict(asset="historical_documentary_execution_record",status="READY_DOCUMENTARY_ONLY",path=str(path),bytes=path.stat().st_size,sha256=sha(path)))
    config=ROOT/f"artifacts/v2_runtime_assets/hf/hub/models--monologg--koelectra-base-v3-discriminator/snapshots/{repro['requested_model_revision']}/config.json"
    if config.is_file():
        cfg=read_json(config)
        assets.append(dict(asset="base_encoder_config_not_checkpoint_metadata",status="READY_BASE_CONFIG_ONLY",path=str(config),bytes=config.stat().st_size,sha256=sha(config),
            config={k:cfg.get(k) for k in ("model_type","hidden_size","embedding_size","num_hidden_layers","num_attention_heads","intermediate_size","vocab_size","max_position_embeddings","type_vocab_size")}))
    asset_report=dict(assets=assets,source_commit="9bab7e383928426e2d866de90acae013fe1f7d86",
        historical_model_training_config=dict(status="DOCUMENTED_NOT_CHECKPOINT_VERIFIED",**repro["training"]["training_config"]),
        historical_input_contract=dict(max_history=5,max_sequence_length=512,label_order=repro["label_order"]),
        independent_v1_split=dict(status="NOT_FOUND",documented_independent_validation_available=False,documented_independent_test_available=False,
            evaluation_set="TRAIN (IN-SAMPLE)",note="No historical held-out split to recover; splits.py is future planning code."),
        exact_training_code_snapshot=dict(status="NOT_FOUND",documentary_state="not_recorded",head_during_training=repro["current_code_commit"]),
        checkpoint_model_loading="BLOCKED_FILE_MISSING",human_approval_assigned=False)
    (OUT/"asset_inventory.json").write_text(json.dumps(asset_report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    summary=dict(human_review_utterances=len(rows),new_train_multilabel_cases=len(multi),
        new_normal_conversations=4,validation_normal_conversations=8,normal_utterance_coverage=96,
        semantic_scenario_pairs=len(pair_rows),v1_conversation_index=len(index),asset_records=len(assets),
        status="NEEDS_HUMAN_REVIEW",human_approval_assigned=False)
    (OUT/"review_queue_summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__ == "__main__":
    main()
