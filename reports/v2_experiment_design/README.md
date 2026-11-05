# v1 재학습 기준과 A/B/C 공정 비교 준비

**실험 계획·독립 설정·공개 기반 모델·CPU 사전 검증을 준비했습니다. 실제 학습은 수행하지 않았고 아직 시작 승인 상태도 아닙니다.** 새 A 모델은 `v1_retrained_baseline`이며 과거 v1 체크포인트 복원본이 아닙니다.

|항목|상태|실제 결과 또는 계획|
|---|---|---|
|과거 recipe 확인|READY / 일부 UNKNOWN|모델·입력·손실·1 epoch·LR 등 확인. 미커밋 코드 snapshot·실제 v1 metadata·일부 optimizer 세부 기록은 미확인|
|공개 기반 encoder·tokenizer|READY|고정 revision 파일 다운로드·해시 검증·오프라인 실제 encoder 로딩 성공|
|A/B/C 독립 설정|READY — DESIGN|입력·split·가중치 SHA, 시드 42/43/44, 출력 경로 분리, 학습 비활성화|
|기본 분할|BLOCKED — 후보 검토 필요|엄격 정책 61/4/3, 조건부 현실 후보 48/10/10. 후자는 미승인 짧은 정상 응답 예외 128건이 있음|
|평가 정답 품질|BLOCKED|v1 후보 holdout 20대화·517발화의 독립 검수 필요; 과거 학습 사용 승인과 구별|
|A/B 실제 DataLoader|PASS — 기술 검증만|각 arm에서 943/330/187샘플, 118/42/24 CPU 배치. 모델 예측·TEST 점수 계산 없음|
|C 입력|BLOCKED — 의도된 차단|합성 TRAIN 최종 승인 0개; 미승인 추가나 조용한 누락 실행 금지|
|자동 테스트|PASS|22개: 설정·해시·그룹 누출·재현 시드·출력 덮어쓰기 차단·loss·N/A 지표 검사|
|실제 모델 학습·최적화|NOT_RUN|optimizer·backward·task checkpoint 생성 0|

현재 자료의 희귀 라벨은 완전한 8종 평가를 뒷받침하지 못합니다. 앱 설치 양성 6개가 모두 같은 source 그룹에 있어 TRAIN/VALIDATION/TEST에 분산할 수 없고, 조건부 TEST에는 앱 설치·비밀유지 양성이 없습니다. 해당 지표는 N/A이며 6개 유형의 정의 가능한 macro를 8종 전체 결과라고 보고하지 않습니다.

## 계획 문서와 설정

|파일|내용|
|---|---|
|[v1_retraining_plan.md](v1_retraining_plan.md)|확인한 recipe·미확인 부분·새 baseline 정체성·공개 encoder 확보|
|[split_and_leakage_plan.md](split_and_leakage_plan.md)|가능한 분할 비율·두 후보·그룹/예외·희귀 라벨·TEST 동결 절차|
|[comparison_protocol.md](comparison_protocol.md)|A/B/C·단일 변경·계산량 통제·지표·3시드·paired 불확실성·FP/FN 분석|
|[실험 실행 README](../../experiments/koelectra_v2/README.md)|재현 명령·코드 경계·출력 경로|
|[A.json](../../experiments/koelectra_v2/configs/A.json) / [B.json](../../experiments/koelectra_v2/configs/B.json) / [C.json](../../experiments/koelectra_v2/configs/C.json)|독립적인 실행 설정|
|[split_candidate.json](../../experiments/koelectra_v2/split_candidate.json)|엄격 그룹 분할 진단 후보|
|[split_review_candidate.json](../../experiments/koelectra_v2/split_review_candidate.json)|70/15/15 목표의 조건부 48/10/10 후보·membership·라벨 분포·seed|
|[type_loss_weight_plan.json](../../experiments/koelectra_v2/type_loss_weight_plan.json)|B/C가 함께 쓰는 원래 TRAIN 전용 가중치|
|[public_base_assets.json](public_base_assets.json)|모델 파일 실제 크기·SHA·원격 blob/LFS 대조|
|[preflight_A.json](preflight_A.json), [preflight_B.json](preflight_B.json), [preflight_C.json](preflight_C.json)|실제 CPU 실행과 C 차단 결과|
|[automatic_tests.json](automatic_tests.json), [requirements-lock.txt](requirements-lock.txt)|실행한 22개 테스트와 현 환경 버전|

## 사람 검토 우선순위

|우선순위|대상|조치|
|---|---|---|
|P0 — 분할/평가 사용 차단|의미적 시나리오 9쌍, 합성 승인 0건, 짧은 정상 응답 교차 예외 128건, 제안 holdout 517발화|동일 가족 여부·예외 허용·정답 품질·학습 사용 결정을 먼저 확인. 예외가 거부되면 연결 그룹과 모든 split/config를 학습 전에 다시 동결|
|P0/P1 — 기존 검토 사례|기존 132발화: P0 11·P1 119·P2 2|멀티라벨 3개, 0020의 선입금형 기제, 정상 경계·미래 문맥을 알아야 하는 초기 사칭 라벨 확인|
|P0 조사 유지|v1과의 유사도 0.814815 문장 1쌍|현재 v1 원문은 TRAIN 후보. 일반 신청 부인 표현의 유사성이며 확정된 시나리오 중복으로 단정하지 않음|
|P2 — 유지 여부 기록|기존 TRAIN 동일 문장 1쌍|자동 삭제·라벨 수정 없이 사람 결정 기록|

검토 자료는 [prioritized_existing_132.csv](prioritized_existing_132.csv), 기존 [시나리오 9쌍 전체 원문](../v2_pipeline_audit/semantic_scenario_pairs.csv), [short_normal_exception_review.csv](short_normal_exception_review.csv), [v1_proposed_holdout_gold_review.csv](v1_proposed_holdout_gold_review.csv)입니다. 파일 간 주제가 겹치므로 이 개수들을 독립 표본 수로 합산하지 않습니다. 원래 검수 CSV와 별도이며 사람 승인 값은 만들지 않았습니다.

합성 TRAIN 후보와 제안된 공통 holdout의 추가 문자열 107,536쌍에서는 완전·정규화·0.80 이상 후보가 0이었습니다. [검사 결과](synthetic_vs_proposed_holdouts.json)는 문자열 검사일 뿐 의미적 독립성 증명이 아닙니다. 이전의 132발화·9쌍은 여전히 검토 대상이며 중복 확정 자료로 바꾸지 않았습니다.

## 학습 시작 전 순서

1. 출처/시나리오 가족·짧은 정상 표현 예외·기존 의미적 검토를 사람이 판단합니다. 임계값/모델 성능을 보며 split을 고르지 않습니다.
2. 평가 후보 517발화의 라벨과 가이드를 검증하고 필요한 변경은 별도의 승인된 버전에서 처리합니다. 기존 v1 입력은 그대로 보존합니다.
3. 승인된 분할·gold·입력·모델 자산·가중치·시드·프로토콜 SHA를 동결하고 TEST를 봉인합니다. 실제 학습 사용 결정을 확보합니다.
4. A의 과거 recipe, B/C의 새 loss, 전용 출력 예약·checkpoint writer와 holdout evaluator를 미래 학습 진입점에 연결하고 검증합니다. 현재 preflight 도구를 학습 CLI로 간주하지 않습니다.
5. C는 승인된 합성 TRAIN만 추가하고 공통 holdout과의 가족 누출을 재확인합니다. B/C 가중치는 재계산하지 않습니다. 최종 C 크기에 따라 step-matched 보조 통제의 예산을 먼저 고정합니다.
6. 승인 후 같은 3시드·같은 평가 자료로 실험합니다. 현재는 그 학습·threshold 최적화·TEST 예측을 모두 실행하지 않았습니다.

기존 입력·정본·검수·이전 보고서·코드·런타임 1,073개 파일은 사전 해시로 보호했습니다. 실제 최종 보존 확인은 [artifact_manifest.json](artifact_manifest.json)에 기록합니다. 기존 v1 checkpoint 경로를 새 가중치로 대체하지 않았고 Commit·Push·PR 생성도 수행하지 않았습니다.
