# 다음 단계 의존성과 12단계 완료 기준

2차는 실제 학습을 시작하는 단계가 아니라 기존 코드 재사용·통합 단계다. 파일이 없는 미래 manifest를 존재한다고 가정하지 않는다. 다음의 예정 이름은 이번 설계 계약의 `future_required`와 일치하며 내용·권한·해시를 확보한 뒤 새 버전에 동결한다.

## 재사용할 실제 코드

공통 기준 디렉터리는 `artifacts/v1_reference/pr35_9bab7e383928/risk_speech_ai/`다. 고정 스냅샷은 감사 근거로 보존하고 신규 production adapter는 `experiments/koelectra_v2/` 아래 별도 모듈로 작성한다.

|파일·함수|재사용 목적|통합 시 주의|
|---|---|---|
|`model.py:RiskSpeechClassifier`|공통 encoder·1/8 head|구조/라벨 순서 변경 금지|
|`training_data.py:TrainingSample, build_training_samples` 및 `train_cli.py:build_safe_training_samples`|현재 발화 타깃·안전 문맥 구성|기존 단일 검수 상태만으로 최종 사용 승인 추정 금지|
|`tokenization.py:build_model_input, load_koelectra_tokenizer`|5발화/512·현재 보존|고정 tokenizer/어휘 검증|
|`dataset.py:RiskSpeechDataset, DynamicPaddingCollator, make_training_dataloader`|실제 CPU batch|train/validation/test loader를 명시적 manifest로 분리|
|`training.py:TrainingConfig, set_training_seed, create_training_model, compute_losses, train_model`|기본 loop·seed·로그 참조|원본 loss는 무가중; 그대로 새 B라고 부르면 안 됨|
|`inference.py:logits_to_outputs, infer_batch, load_checkpoint_inference`|sigmoid/threshold 및 추론|새 metadata와 vector threshold 검증 연결|
|`metrics.py:binary_metrics, multilabel_metrics`|정의 불가 지표 처리|유형별 vector threshold 적용 후 집계 adapter 필요|
|`checkpoint.py:validate_checkpoint_metadata, validate_tokenizer`|모델/입력 호환 검사|신규 split/protocol/승인/threshold metadata 보완|
|`dataset/scripts/v2_pipeline_gate.py:approval_audit, prepare_partition`|기존 합성의2인검수+사용승인·preflight 구분|현재는 합성 train/validation만 지원. 인간작성/권한/봉인test용 별도 adapter 필요|
|`experiment_runtime.py:loss_values, output_path, reserve_output`|가중 BCE와 덮어쓰기 거부 패턴|기존 schema=1epoch/0.5/상한5 전용. 신규 JSON을 입력하지 말 것|
|`plan_splits.py`, 기존 중복 검사·검수 queue 코드|출처·중복 연결 그룹 검토 재사용|48/10/10 manifest는 신규 전략에 연결하지 않음|

## 2차에 실제로 추가해야 할 코드(아직 없음)

예정 모듈은 `expanded_data.py`(역할·가족·출처·권한·gold hash·승인 대조), `expanded_training.py`(TRAIN-only 비율 weight·1~3epoch/step limit), `expanded_selection.py`(VALIDATION epoch/threshold 선택), `expanded_evaluation.py`(봉인영수증·공통 metrics·정상FP·최종 평가), `expanded_checkpoint.py`(전용 output 예약/metadata), `expanded_cli.py`(명시적 preflight/train/select/final-evaluate 모드)다. 이름은 구현 시 변경 가능하지만 해당 책임은 모두 필요하다. 기존 고정 PR35 CLI를 수정해 과거 재현 근거를 훼손하지 않는다.

구현 순서는 설정 parser/validator → manifest·권한 adapter → no-overwrite writer → weighted loss/loop 주입 → 독립 validation selector → 최종 evaluator다. fixture와 fake logits로 누출 거부·미승인 거부·hash mismatch·zero-positive·동률·재실행 덮어쓰기·TEST 조기접근을 검증한다. 실제 데이터 학습·TEST 추론은 9단계 이후의 권한과 입력이 갖춰질 때까지 열지 않는다.

## 12단계 실행 계약

|단계|필요한 실제/미래 입력|완료 조건|사람 결정·차단 조건|
|---|---|---|---|
|1 기존 자료·기준 확정(이번)|원격0132398, 복구입력, 기존 A/B/C/검수·보고서, 이번 지침|4종 문서·별도 JSON·참조 검증·전후 해시·회귀 결과·안전 Git 동기화 기록|원본 추진안 목표·성능합격 수치 미확인은 숨기지 않고 추후 동결 항목으로 남김|
|2 A/B/C 학습·평가 코드 완성|이번 protocol JSON, 위 재사용 코드/실제 테스트, `inventory.json`|신규 adapter/CLI·weighted loop·epoch/threshold·metadata·보호·fixture 검증 완료. 실제 학습 불필요|사람 승인 없이 code 구현 가능. 실제 실행은 계속 차단|
|3 TRAIN 추가1차14|기존24 정본/출처·가족, 검수 queue; 미래 `v2_expansion_v1/batch_01.jsonl`, source manifest|14개 실제 작성 후보·권한·생성방법·정규화/의미 중복 점검·검수표 준비, 누적38|인간7/LLM4/허가증강3; 실제 작성자·권리자 필요|
|4 TRAIN 추가2차14|누적38/가족 registry; 미래 `batch_02.jsonl`|같은 조건14개, 누적52|앞 차수와 가족·파생 중복 금지|
|5 TRAIN 추가3차14|누적52; 미래 `batch_03.jsonl`|같은 조건14개, 누적66|수량을 위해 위험 라벨 과다 부여 금지|
|6 TRAIN 추가4차14|누적66; 미래 `batch_04.jsonl`|같은 조건14개, 누적80, 유형 부족·지원 가족 재집계|미달 양성목표는 사람이 설계 개정, 가짜 충족 금지|
|7 독립 VALIDATION32|TRAIN family/source registry, 신규 인간작성·권한·gold evidence; 미래 `independent_validation_32_manifest.json`|새32개·독립 가족·검수 gold·hash 동결, LLM24와 별개|작성자·독립 검수자 실제 판단; 목표 coverage 미달은 제한|
|8 봉인 TEST40|독립 평가 담당자, TRAIN/VAL 예약 registry; 미래 `dataset/05. metadata/v2_sealed_test_40_receipt.json`|담당자가 새40개 권한/검수/gold/해시를 모델 선택 전에 봉인, 개발에는 영수증만 제공|본문·정답 저장소와 권한은 담당자 관리; 개발자는 접근 금지|
|9 검수·학습 사용 승인|기존 `human_review_working.csv`, `human_review_new8.csv`, 신규 배치 검수, v1 출처 권한 evidence; 미래 `eligible_v1_train_manifest.json`, `approved_train_80_manifest.json`|정본과결정 해시 연결, 두 사람 독립검수·최종 합의·사용허가, unresolved0, 전 arm 입력 동결|김해린·임정윤 등 지정 검수자/책임자·권리자의 실제 결정 필요. 문서상 pass/PR merge만으로 승인하지 않음|
|10 기준·설정 개선 학습|완성 trainer, 적격 v1 manifest, 독립 validation gold, TEST 봉인 영수증, 승인 결정, 환경 lock|A0/A_epoch/B_ratio의 등록3seed 학습·B epoch/threshold 선택·새 경로 metadata/해시·로그 저장|9단계 이전 학습 금지. TEST를 열어 선택하지 않음|
|11 승인 합성 보강 학습|B에서 동결한 recipe/weights/threshold, approved80, 같은 초기 encoder/seed|C 및 B_step_matched 로그·checkpoint, step·시간·데이터 양 차이 명시|미승인 자료 사용/승인0일 때 C를 B로 조용히 대체 금지|
|12 최종 평가·인계|선택 동결문서, 모든 checkpoint·protocol/data hash, 평가 담당자의 봉인 TEST·gold|한 최종 평가 작업에서 등록 arm/seed 비교·지원 수/불확실성/정상오탐/희소유형·재현명세·v2 checkpoint hash와 인계|평가 담당자 접근결정 필요. 같은 TEST에 재튜닝해 개선 주장 금지|

예정 경로의 `v2_expansion_v1`는 `dataset/04. processed/` 아래다(봉인 영수증 제외). 이번에는 이런 파일의 내용·대화 본문·승인 결정을 만들지 않았다. TEST40 계획도 본문 생성이 아니다.

2차 착수는 가능하지만 실제 학습과 성능 합격 판단은 불가하다. 미해결 사항은 원본 추진안 수치, v1 실제 사용 권한과 의미적 가족, 기존 검수132발화/9쌍 및 유사1쌍, TRAIN80·독립32·봉인40 실물/승인, 신규 실행 코드, 현재 발견한 v1 checkpoint의 metadata/로드 확인이다. 그중 128예외·517미검수·TEST양성0은 보존한 과거48/10/10 후보의 문제이며 신규 benchmark의 충족 증거로 사용하지 않는다.
