# KoELECTRA v2 TRAIN 추가 8대화와 통합 후보

신규 **8대화·72발화**와 기존 16대화를 합친 **24대화·208발화 통합 후보**를 만들고, 실제 CPU DataLoader에서 52개 미니배치를 생성했습니다. 현재 상태는 자동 검증 통과·사람 검수 대기이며 **실제 학습 준비 완료 상태가 아닙니다**.

|구분|기존 16대화|신규 8대화|통합 24대화|
|---|---:|---:|---:|
|발화 수|136|72|208|
|피싱 발화|34|19|53|
|정상 발화|102|53|155|
|완전히 정상인 대화|6|4|10|
|멀티라벨 발화|3|3|6|
|양성 라벨 합계|37|22|59|

|위험 유형|기존|신규|통합|
|---|---:|---:|---:|
|institution_impersonation|10|4|14|
|money_transfer|3|4|7|
|personal_information|4|5|9|
|app_installation|7|0|7|
|secrecy|5|1|6|
|threat_pressure|3|1|4|
|loan_fraud|3|3|6|
|information_probing|2|4|6|

기존 TRAIN에서 상대적으로 적은 정보 탐색·금전 이전·개인정보·대출 미끼를 보완했습니다. 앱 설치는 기존 7개가 있어 신규에 억지로 추가하지 않았습니다. 신규 피싱 상황은 거래처 청구서 수취 계좌 바꿔치기, 가짜 연구 지원자 선별, 학자금의 장학금 자동 전환 사기, 투자 피해 회수 사기입니다. 정상 상담은 기념주화 교환 예약, 본인 문서 수령, 방재 훈련 안내, 대여 노트북 반납 전 데이터 삭제입니다. 피싱 4대화는 각각 10발화, 정상 4대화는 각각 8발화입니다.

## 자동 검사와 중복

|검사|실제 결과|
|---|---|
|JSONL 구조·순서·라벨·마스킹·CSV·보존 등|최종 1,580개 검사 통과, 실패 0|
|검증 코드 테스트|16개 통과, 실패·오류 0; 메모리 복사본 오류 주입 및 덮어쓰기 거부 검사|
|신규 ↔ 기존 TRAIN 발화|9,792쌍; 완전·정규화·유사도 0.80 이상 후보 모두 0; 최고 0.549020|
|신규 내부 발화|2,556쌍; 후보 0; 최고 0.439024|
|통합 TRAIN 내부|21,528쌍; **기존 동일 문장 1쌍 유지**, 추가 중복 0|
|신규 ↔ VALIDATION 발화|13,824쌍; 후보 0; 최고 0.638298|
|통합 ↔ VALIDATION 발화|39,936쌍; 후보 0|
|신규 전체 전개 ↔ 기존 TRAIN|128쌍; 후보 0; 최고 0.230241|
|신규 전체 전개 ↔ VALIDATION|192쌍; 후보 0; 최고 0.253906|
|신규 전체 전개 내부|28쌍; 후보 0|
|TRAIN 내부 ID·가족·시나리오 ID|통합 24개 모두 유일|
|TRAIN ↔ VALIDATION ID·가족·시나리오 ID|모두 충돌 0|
|기존 데이터·검수·코드·런타임 보존|사전 기록한 940개 파일 SHA-256 모두 동일|
|브랜치·HEAD|`feat/koelectra-v2-pilot-readiness`, `d8c9fb2834f64ff2027b0a0a43a490563f91c80c` 유지|

정규화는 NFKC·casefold 후 공백과 Unicode 구두점 제거입니다. 유사도는 `SequenceMatcher(autojunk=False)`이며 0.80 이상 후보를 빠짐없이 기록합니다. 중복 후보는 삭제하지 않습니다. 기존 동일 문장은 **SYN2-TRAIN-0003-4 ↔ SYN2-TRAIN-0006-4**의 `제가 이해를 못 할 수도 있어서 같이 듣자는 건데요.`입니다. 내용·라벨·검수 기록을 변경하지 않았습니다.

문자열 검사와 별도로 [시나리오 전개 비교](scenario_independence_review.md)에 신규 8개와 기존 TRAIN·VALIDATION의 관련 가족, 공유하는 상위 위험 기제, 다른 진행 단계를 기록했습니다. 의미적 독립성은 생성자의 사후 검토이며 독립적인 사람 확인 전입니다. **0020의 자산 회수 사기는 기존 선입금형 사기와 상위 기제를 공유하므로 우선 검수 대상**입니다. 자동 문자열 검사 통과를 의미적 독립성 증명으로 보고하지 않습니다.

## 실제 CPU 실행

|항목|결과|
|---|---|
|환경|기존 `.venv-v2`, Python 3.12.14, torch 2.6.0+cpu, transformers 4.57.6|
|기존 런타임|PR35 고정 커밋 `9bab7e383928426e2d866de90acae013fe1f7d86`, 소스 해시 일치|
|토크나이저|실제 KoELECTRA, revision `68b30cd259f34a4b5aa8786392612ba2a2617fcc`, 기존 어휘 해시 일치|
|전체 실행 검사용 샘플 변환|24대화의 208발화 모두 변환|
|Dataset / DataLoader|기존 `RiskSpeechDataset` / 실제 `torch.utils.data.DataLoader`|
|배치|batch size 4, CPU에서 52개 모두 생성|
|첫 배치 입력|input_ids·attention_mask·token_type_ids 각각 [4,83], int64|
|이진 / 8유형 타깃|[4,1] / [4,8], float32|
|문맥|동일 대화의 이전 최대 5발화, 208타깃 전체 일치|
|토큰·마스크·패딩·라벨|52배치 전체 실제 값 검증 통과|
|토큰 길이 / 제거한 문맥|20~163 / 0|
|기존 안전 샘플 생성기|기존 136개만 포함, 신규 미검수 72개는 제외|

미검수 발화까지 실제 배치 실행을 확인하기 위해 기존 `TrainingSample` 타입에 208개를 담는 **실행 검증 전용 어댑터**를 사용했습니다. 기존 136개의 어댑터 라벨 상태는 원래의 `reviewed`를 유지하며 이것은 기존 1인 검수 후보 매핑입니다. 신규 72개는 모두 `unreviewed`입니다. 실행 검사용 파일은 `execution_check_only=true`, `training_authorized=false`, `training_eligible=false`, `final_approved=false`이며 학습 CLI를 실행하지 않습니다.

일반 `build_safe_training_samples`는 1차에서 신규 미검수 72개를 제외합니다. 2차에서는 그 본문도 문맥에서 제거하므로 통계는 `missing_tuned_text=72`, `included=136`입니다. 이 2차 통계를 `excluded_unreviewed=72`로 기대했던 **검증 코드의 첫 실행은 실패**했습니다. [최초 실패 기록](execution_initial_attempt.json)을 보존하고, 1차 제외 수와 2차 안전 재구성 수를 각각 확인하도록 코드를 수정했습니다. 해당 동작의 회귀 테스트를 추가하고 전체 CPU 검사를 재실행해 통과했습니다. 데이터 수정·삭제·재라벨링은 없었습니다.

## 산출물과 생성 이력

|산출물|경로|
|---|---|
|신규 8대화 정본 후보|[train_0017_0024_generated.jsonl](../../dataset/04.%20processed/v2_train_expansion/train_0017_0024_generated.jsonl)|
|통합 24대화 후보|[train_24_mixed_review_candidate.jsonl](../../dataset/04.%20processed/v2_train_expansion/train_24_mixed_review_candidate.jsonl)|
|생성 근거·모델·입력 해시·시나리오|[generation_and_scenarios.json](../../dataset/04.%20processed/v2_train_expansion/generation_and_scenarios.json)|
|신규 설계표|[scenario_design.md](scenario_design.md)|
|사후 전개 비교·사람 검토 필요 항목|[scenario_independence_review.md](scenario_independence_review.md)|
|중복 전체 후보·최고 유사 쌍|[duplicate_report.json](duplicate_report.json)|
|자동 검사·CPU 실제 결과|[validation_result.json](validation_result.json)|
|신규 72발화 2인 검수표|[human_review_new8.csv](../../dataset/review/v2_train_expansion/human_review_new8.csv)|
|검수 지침|[검수 README](../../dataset/review/v2_train_expansion/README.md)|
|신규 작성·통합 코드|[prepare_v2_train_expansion.py](../../dataset/scripts/prepare_v2_train_expansion.py)|
|중복·품질·CPU 검증 코드|[validate_v2_train_expansion.py](../../dataset/scripts/validate_v2_train_expansion.py)|
|회귀·오류 탐지 테스트|[test_v2_train_expansion.py](../../tests/test_v2_train_expansion.py)|
|실제 테스트 결과|[expansion_unit_tests.json](expansion_unit_tests.json)|
|보존 기준 해시|[protected_baseline.json](protected_baseline.json)|
|실행 검사용 어댑터|`dataset/04. processed/v2_train_expansion/cpu_dry_run_label_candidates.jsonl`, `cpu_dry_run_text_candidates.jsonl`|
|문맥 발화 ID 목록|`dataset/04. processed/v2_train_expansion/context_audit.jsonl`|

신규 ID는 `SYN2-TRAIN-0017`~`0024`, 가족은 `FAM2-TRAIN-0017`~`0024`입니다. 모델은 세션에서 확인되는 `GPT-6 (Codex)`로 기록했고, 세부 백엔드 모델 ID는 확인할 수 없어 null로 명시했습니다. 권장 `GPT-6.1 Sol`을 사용 모델로 추정하지 않았습니다. 작업 시작 기록은 `2026-11-05T17:21:24.646507+09:00`입니다. Python 코드는 이 세션에서 작성한 대화 리터럴을 직렬화하며 모델 API를 추가 호출하지 않습니다.

신규 JSONL의 생성 이력은 `human_approved=false`입니다. 통합 후보의 앞 16대화는 기존 1인 검수 후보 파일의 **바이트 그대로**이며 `review_preparation`과 승인 근거도 그대로입니다. 뒤 8대화는 `review_status=generated`이고 사람 승인 필드를 새로 만들지 않았습니다. 신규 CSV는 김해린·임정윤과 최종 합의 모두 72행 미승인, 검수 시각과 의견은 공란, 학습 반영은 미반영입니다.

생성 스크립트는 VALIDATION 본문을 읽지 않습니다. 예약 registry는 제외 목록으로만 확인하고, 본문은 신규·통합 파일의 생성 해시 확인 뒤 검증 코드에서 중복 검사에만 사용했습니다. VALIDATION의 라벨 분포나 어려운 사례에 맞추어 신규 데이터를 조정하지 않았고 생성 후 원문 해시는 그대로입니다. 같은 대화 세션에 앞선 VALIDATION 작성 이력이 있으므로 완전한 블라인드 모델 생성 실험이라는 주장은 하지 않습니다.

## 사람 검수와 학습 준비 상태

사람은 신규 72발화의 자연스러움·발화별 위험 행위·더미 및 마스킹을 확인해야 합니다. 0017-7의 송금·은폐, 0019-6의 허위 대출 보장·비밀번호 수집, 0020-9의 송금·시한 압박 멀티라벨을 중점 확인합니다. 0018의 명의·이력 탐색과 정확한 식별정보 요구를 구별하고, 정상 4대화의 본인 확인·현장 통제·개인자료 보호 표현을 검토합니다. 기존 동일 문장 1쌍과 0020의 시나리오 의미적 유사성은 삭제 없이 검토 의견을 남깁니다.

**실제 학습은 아직 시작할 수 있는 승인 상태가 아닙니다.** 신규 8대화는 두 사람 검수 전, 기존 16대화는 1인 검수 후보이며 김해린·최종 합의는 미승인입니다. 24대화 통합 후보를 학습에 사용하지 않았습니다. 실제 v1 학습 입력 미확보로 v1 중복 검사는 미검증이고 TEST는 미생성입니다. 모델 학습·순전파·임계값 조정·v1 체크포인트 변경·Commit·Push·PR 생성은 수행하지 않았습니다.

## 재실행

```powershell
& '.venv-v2/Scripts/python.exe' -B -X utf8 dataset/scripts/prepare_v2_train_expansion.py
& '.venv-v2/Scripts/python.exe' -B -X utf8 dataset/scripts/validate_v2_train_expansion.py
& '.venv-v2/Scripts/python.exe' -B -X utf8 -m unittest discover -s tests -p test_v2_train_expansion.py -v
```

생성 파일이나 검수표가 이미 존재하고 내용이 다르면 생성기는 덮어쓰지 않고 중단합니다. 자동 검증은 최초 미승인 준비 상태를 확인하므로 사람이 CSV를 편집한 뒤에는 불일치를 보고할 수 있습니다. 그 경우 실제 검수 기록을 초기화하지 마세요. 검증 보고서는 재실행 시 갱신되지만 최초 실패 기록과 기존 자료는 보존됩니다.
