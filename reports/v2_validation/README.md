# KoELECTRA v2 독립 합성 VALIDATION 24대화

2026-11-05에 신규 작성한 **24대화·192발화가 자동 검사와 실제 CPU DataLoader 검증을 통과**했습니다. 사람 검수 전 후보이며 모든 대화는 `review_status=generated`입니다. 김해린·임정윤 및 최종 합의 결과는 각각 192행 모두 미승인입니다.

|항목|실제 결과|
|---|---|
|대화 / 발화|24 / 192, 각 대화 8발화|
|피싱 상황 / 완전 정상 상담|16 / 8대화|
|피싱 / 정상 발화|60 / 132|
|양성 라벨 합계 / 멀티라벨 발화|61 / 1|
|TRAIN 발화 비교|192 × 136 = 26,112쌍|
|TRAIN 완전 일치 / 정규화만 일치|0 / 0|
|TRAIN 유사도 ≥ 0.90 / 추가 검사 ≥ 0.80|0 / 0|
|TRAIN 대비 최고 발화 유사도|0.507042, VALIDATION 0002-7 ↔ TRAIN 0003-3|
|TRAIN 전체 대화 최고 유사도|0.252212, 24 × 16대화 비교|
|VALIDATION 내부 비교|18,336쌍; 완전·정규화·0.80 이상 중복 0, 최고 0.562500|
|시나리오 가족 / 시나리오 ID / 대화 ID 충돌|로컬 기존 processed JSONL 8개와 비교, 모두 0|
|JSONL / 라벨 / 순서 / 마스킹 / CSV|통과; 세부 결과는 `validation_result.json`|
|실제 Dataset / DataLoader|고정 PR35 구현과 KoELECTRA 토크나이저 사용; 192샘플 / 48개 CPU 배치|
|문맥|동일 대화의 이전 최대 5발화, 192개 타깃 전체 검증; 타 대화 유입 0|
|토큰 길이 / 제한으로 제거한 문맥|18~144 / 0|
|첫 배치 입력 / 이진 타깃 / 8유형 타깃|[4,94] / [4,1] / [4,8]|
|dtype / 장치|입력 int64, 타깃 float32 / 모두 CPU|
|학습 입력 차단|기존 샘플 생성기가 `unreviewed` 192개 전부 제외, 학습 샘플 0개|
|검증 코드 오류 탐지 테스트|13개 통과, 실패·오류 0; 메모리 복사본만 손상시켜 검사|
|기존 자료 보존|사전 기록한 923개 파일 SHA-256 모두 동일|
|Git|브랜치·HEAD 동일; Commit / Push / PR 생성 없음|

|위험 유형|양성 발화 수|해당 유형을 포함한 대화 수|
|---|---:|---:|
|institution_impersonation|14|14|
|money_transfer|8|7|
|personal_information|10|7|
|app_installation|5|3|
|secrecy|7|7|
|threat_pressure|6|4|
|loan_fraud|4|2|
|information_probing|7|5|

금전 이전과 시한 압박이 함께 표현된 0005-6만 멀티라벨입니다. 피해자의 질문·인용·거절에는 상대 발화의 라벨을 상속하지 않았습니다. 정상 사례는 카드 해외 거래 차단, 착불 거절, 반품 배송비, 조건부 대출 견적, 숙박 예약 확인, 동의 기반 원격지원, 냉장 배송 인계, 가족 금융정보 공개 제한입니다.

## 결과물

|구분|경로|
|---|---|
|정본 후보|[validation_24_generated.jsonl](../../dataset/04.%20processed/v2_validation/validation_24_generated.jsonl)|
|가족 예약 목록·생성 이력|[scenario_registry.json](../../dataset/04.%20processed/v2_validation/scenario_registry.json)|
|상황·기제·TRAIN과의 차이·검토 초점|[scenario_design.md](scenario_design.md)|
|2인 검수 CSV, UTF-8 BOM|[human_review.csv](../../dataset/review/v2_validation/human_review.csv)|
|검수 방법|[검수 README](../../dataset/review/v2_validation/README.md)|
|신규 작성 원문 및 재현 코드|[generate_v2_validation.py](../../dataset/scripts/generate_v2_validation.py)|
|구조·중복·CPU 배치 검증 코드|[validate_v2_validation.py](../../dataset/scripts/validate_v2_validation.py)|
|검증 코드 테스트|[test_v2_validation.py](../../tests/test_v2_validation.py)|
|전체 기계 판독 결과|[validation_result.json](validation_result.json)|
|중복 상세·비교 범위|[duplicate_report.json](duplicate_report.json)|
|기존 자료 사전 해시|[protected_baseline.json](protected_baseline.json)|
|미검수 평가용 라벨·본문|`dataset/04. processed/v2_validation/evaluation_label_candidates.jsonl`, `evaluation_text_candidates.jsonl`|
|문맥 ID 검증 기록|`dataset/04. processed/v2_validation/context_audit.jsonl`|

## 생성 및 변경 이력

- 생성자는 이 Codex 세션의 `GPT-6 (Codex)`입니다. 권장 모델명 `GPT-6.1 Sol`을 실제 사용 모델로 추정하지 않았습니다. 세부 백엔드 모델 식별자는 세션에서 확인할 수 없어 registry에 `null`과 사유를 기록했습니다.
- `2026-11-05T16:55:29+09:00`는 이번 신규 작성 작업의 기록 시점입니다. Python 스크립트는 세션이 작성한 대화 리터럴을 JSONL로 직렬화하며 별도 모델 API를 호출하지 않습니다. 생성 버전은 `v2-validation-24-1`입니다.
- 모든 대화의 `revision_history`에 신규 생성, 모델, 해당 발화 ID 및 `human_approved=false`를 기록했습니다. 기존 TRAIN 정본·검수·후보의 내용 또는 승인 상태는 수정하지 않았습니다.
- 최초 출력 후 데이터 삭제·재라벨링·대화 교체는 없었습니다. 자동 검사에서 데이터 수정이 필요한 오류는 발견되지 않았습니다. 검증 코드에는 대화 길이에 의존하지 않는 문맥 조회와 유형별 대화 수 집계를 보완했습니다.
- 원본 스키마에 맞춰 `utterance_id`는 대화 안에서 1~8입니다. 전역 식별자는 `(synthetic_id, utterance_id)` 또는 검수 CSV의 결합 ID이며 모두 유일합니다.

## DataLoader 연결 방식

기존 검수 완료 전용 샘플 생성기는 `label_status=unreviewed`를 제외합니다. 이를 우회하려고 `reviewed`나 사람 승인을 부여하지 않았습니다. 평가 전용 어댑터가 생성 라벨을 기존 `TrainingSample` 타입에 담아, 수정하지 않은 PR35의 `RiskSpeechDataset`, `make_training_dataloader`, `DynamicPaddingCollator`에 전달했습니다. 어댑터 파일은 모두 `split=validation`, `evaluation_only=true`, `training_eligible=false`, `final_approved=false`이며 라벨 파일의 상태도 `unreviewed`입니다. 학습 CLI에는 연결하지 않았습니다.

런타임 소스는 `artifacts/v1_reference/pr35_9bab7e383928/`, 고정 커밋은 `9bab7e383928426e2d866de90acae013fe1f7d86`입니다. 토크나이저는 `monologg/koelectra-base-v3-discriminator`, 고정 revision `68b30cd259f34a4b5aa8786392612ba2a2617fcc`이며 어휘 해시를 기존 재현성 보고서와 대조했습니다. `.venv-v2`의 Python 3.12.14, torch 2.6.0+cpu, transformers 4.57.6을 재사용했습니다. 네트워크 다운로드, 모델 로딩, 순전파, 학습, 임계값 최적화, 체크포인트 기록은 수행하지 않았습니다.

## 독립성의 범위와 사람 검토

정규화는 NFKC·casefold 후 공백과 Unicode 구두점을 제거합니다. 유사도는 `SequenceMatcher(autojunk=False)`이며 0.90 이상을 고유사 후보, 0.80 이상을 추가 점검 대상으로 기록했습니다. TRAIN 정본과 1인 검수 후보의 본문 일치를 확인하고 16대화의 모든 발화와 비교했습니다. 생성자는 전체 TRAIN 전개를 읽고 각 신규 시나리오의 차이를 설계표에 적었습니다. 문자열 검사는 의미가 같은 바꿔 쓰기나 같은 사기 전개를 증명 가능하게 배제하지 못하므로 **의미적 독립성은 독립적인 사람 확인 전**입니다.

김해린·임정윤은 각자 192발화를 전후 문맥과 함께 읽고 다음을 확인해야 합니다.

1. 24개 가족이 TRAIN의 단어만 바꾼 전개가 아닌지, 검토표와 TRAIN 원문을 함께 대조합니다. 특히 앱 설치·계정정보 수집 사례의 기제와 전개를 확인합니다.
2. 정상 상담 8개에서 소속 소개, 최소한의 이름·이메일 확인, 착불 결제, 조건부 대출, 동의 기반 원격지원, 타인 정보 비공개가 위험 라벨로 바뀌지 않았는지 확인합니다.
3. 관계·생활 패턴 떠보기와 정확한 식별정보 요구를 구분합니다. 0016의 거주·부재 패턴에 대한 `information_probing` 적용 범위를 확인합니다.
4. 0007·0008의 허위 대출 조건, 0005-6의 송금·시간 압박 멀티라벨, 가짜 기관·조직 소속 주장을 발화 단위로 확인합니다.
5. 자연스러움, 피싱 문맥에서 위험 행위가 없는 정상 발화, 가상 기관명·허용 마스킹 토큰을 확인합니다. 원문 수정이 필요하면 삭제 대신 변경안과 사유를 검수 CSV에 남깁니다.

실제 v1 학습 입력은 미확보이므로 **v1과의 중복 검사는 미검증**입니다. 독립 TEST 파일·manifest도 제공되지 않았으며 로컬 processed 영역에서 TEST 지정 자료가 발견되지 않았습니다. TEST와는 별도 ID 공간을 예약했지만 미확보 TEST의 내용 독립성을 검사했다고 보고하지 않습니다.

24개 가족과 그 전개는 VALIDATION 전용으로 예약했습니다. 이후 TRAIN 8개를 추가하기 전에 `scenario_registry.json`의 가족·상황·위험 기제를 함께 대조해야 합니다. 기존 TRAIN 생성·학습 코드를 변경해 이 예약을 자동 강제하지는 않았습니다.

이 합성 자료는 개발 중 비교를 위한 예비 평가 후보입니다. 실제 보이스피싱 통화에 대한 최종 성능을 입증하지 않으며 이번 작업에서는 정확도·F1 등 모델 성능을 계산하지 않았습니다.

## 재실행

```powershell
& '.venv-v2/Scripts/python.exe' -B -X utf8 dataset/scripts/generate_v2_validation.py
& '.venv-v2/Scripts/python.exe' -B -X utf8 dataset/scripts/validate_v2_validation.py
& '.venv-v2/Scripts/python.exe' -B -X utf8 -m unittest discover -s tests -p test_v2_validation.py -v
```

생성기는 기존 내용이 다르면 덮어쓰지 않고 중단합니다. 검증기는 최초 미승인 준비 상태를 검사하는 도구이므로 사람이 검수 CSV를 편집한 이후에는 실패할 수 있습니다. 그 실패를 없애려고 사람 검수 내용을 초기화하면 안 됩니다. 재실행 시 검증 보고서는 갱신되며 정본·검수 원본은 갱신되지 않습니다.
