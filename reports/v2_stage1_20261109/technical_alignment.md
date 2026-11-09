# KoELECTRA v2 1차 기술 정합성 점검 (2026-11-09 KST)

기준은 원격 `feat/koelectra-v2-pilot-readiness`의 `01323989dad907a38e5fcca9fce0537adc070e32`다. 이번 결과는 실행 기준 확정이며 학습 승인이 아니다. 실제 점검 수치와 파일 해시는 `inventory.json`, 전후 보존 결과는 `preservation_result.json`, 테스트는 `tests.json`에 기록한다.

## Git 동기화와 보존

기본 작업 폴더는 `feat/ai-koelectra-v1-trained-baseline`, HEAD `9bab7e383928426e2d866de90acae013fe1f7d86`이었다. `dataset/README.md`의 Android NER 관련 변경(440줄 추가·58줄 삭제), 미추적 `.tmp/`, `.worktrees/`, `risk_speech_ai/approval_requests_20261027.md`를 확인했다. 이들은 이번 v2 변경으로 판단하지 않아 커밋·푸시 대상에서 제외하고 보존했다. v1 upstream과 당시 HEAD는 동일했다.

origin은 `https://github.com/donggyu567/PIC_AICAMP.git`이다. 요청 브랜치의 로컬 ref가 없어서 fetch 후 `.worktrees/koelectra-v2-pilot-readiness`에 원격을 추적하는 별도 작업 트리를 만들었다. `git pull --ff-only origin feat/koelectra-v2-pilot-readiness` 결과는 `Already up to date.`였다. 요청한 마지막 원격 SHA와 동기화 기준 SHA는 동일하며 기존 v2 미커밋 변경도 없었다. 이번 신규 파일만 선별해 버전 관리한다. force push/reset/PR/merge는 수행하지 않는다.

## 근거 범위

지정된 「PIC_AICAMP KoELECTRA v2 개발 추진안 — 팀장 검토 및 팀원 공유」 원본은 첨부 파일과 로컬 프로젝트 검색에서 확인하지 못했다. A/B/C/D/F/G 절의 기술 항목은 이번 사용자 지침과 실제 저장소 코드로 대조했다. 원본의 정확한 유형별 추가 양성 목표·객관적 합격 수치는 **확인 불가**다. 로드맵·날짜는 기술 정합성 판단에 사용하지 않았다. 원본 대조가 필요한 항목을 임의로 충족 처리하지 않는다.

## 요구사항 대비 판정

|요구사항|판정|실제 근거와 한계|
|---|---|---|
|공통 KoELECTRA encoder, 이진 1·유형 8 출력|일치|PR35 `risk_speech_ai/model.py:RiskSpeechClassifier`, 두 선형 head가 동일 CLS 상태 사용|
|기반 모델·8종 순서 유지|일치|`config.py`, `labels.py`, 기존 A/B/C와 신규 프로토콜 모두 동일; revision `68b30cd259f34a4b5aa8786392612ba2a2617fcc`|
|이전 최대 5발화+현재, 512토큰, 현재 라벨|일치|`training_data.build_training_samples`, `tokenization.build_model_input`, Dataset/Collator; 현재 발화만으로도 초과하면 오류|
|68대화·1,460발화 복구와 입력 해시|일치|정본 labels를 재집계. labels SHA `c205049e1aa2125ad40cc6cea1465b2c2793cc7fedf02b7eab8e1d9f20e9c9e5`; tuned SHA `50ea88cc3ee9c3df1477082ab5daf82ef77f83329374b50f312874592462e6f2`|
|실제 v1 체크포인트 미확보라는 과거 상태|현재 로컬과 불일치|기본 작업 폴더 `artifacts/risk_speech_ai/koelectra_risk_v1.pt`, `checkpoints/risk_speech_v1.pt`에서 각 1,348,308,730 bytes, SHA `1131f9dcc665f79073d98ecd6845573109a89e44dbf2917d299a8fea057020a7` 일치. v2 작업 트리에는 복사하지 않음. 이번에는 로드·추론하지 않았으므로 metadata/동작 검증은 미완료|
|공개 encoder·tokenizer|일치(파일 확인), 로드 미검증|기본 폴더 `.venv-ai/hf-cache/hub`의 고정 revision 공개 가중치 SHA `f3f249cc07826bc2964a2c0dbbd0d239df4fe55efc03ba33e1bd1584cf56c566` 일치. tokenizer 어휘 해시·실제 CPU 실행은 별도 확인. 과거 다른 PC의 절대경로 보고서를 현재 확보 증거로 대신하지 않음|
|TRAIN 24대화·208발화|일치|통합 후보 재집계: LLM 생성 24개, 양성 발화 53개, 유형 양성 합계 59개. 16대화·136발화는 임정윤 1인 검수, 신규 8대화·72발화는 미검수; 최종 승인 0|
|VALIDATION 24대화·192발화|일치(보조 후보)|모두 LLM 생성·미검수. 독립 인간 평가셋으로 승격하지 않음|
|데이터 출처·생성 이력·가족|부분 구현|대화별 source_kind/model/prompt_version/revision_history와 가족 ID 존재. 인간 의미적 독립성 검토는 미완료|
|중복·누출 검사|부분 구현|기존 `independence_result.json`: TRAIN↔보조 VALIDATION 39,936쌍 후보 0; TRAIN↔v1 303,680쌍 중 유사 1쌍(SYN2-TRAIN-0011-2/P0005-5, .814815); 보조 VALIDATION↔v1 280,320쌍 후보 0. TRAIN 내부 기존 동일 문장 1쌍 보존. 문자열 통과는 의미적 독립성 증명이 아님|
|CPU DataLoader|일치(기술 검증)|기존 보고서 208/192발화 52/48배치. 이번 PC 재검증은 `cpu_preflight.json`; preflight 입력이며 학습 적격 판정과 구분|
|기존 v1 방식 1 epoch 기준|부분 구현|기존 A 설정·PR35 학습 loop 존재. 새 독립 평가 전략의 trainer 연결은 없음. A는 과거 학습 가중치 복원이 아니라 공개 encoder에서 새 head로 재학습할 기준 모델|
|1~3 epoch 비교|미구현|기존 A/B/C epoch 1 고정; 신규 버전에 비교 설계만 추가|
|비율 가중치·상한 10|불일치|기존 B/C는 `min(5,sqrt(Nneg/Npos))`; `experiment_runtime.loss_values`에 가중 BCE 있으나 PR35 `compute_losses`와 trainer에는 미연결. 신규 비율 방식은 설계 상태|
|VALIDATION 기반 임계값 선택|미구현|기존 A/B/C는 0.5 고정, 기존 runtime validator도 변경 거부. `type_diagnostics.threshold_rows`는 진단용이며 독립 validation selector가 아님|
|승인된 합성 TRAIN 효과 비교|부분 구현|기존 C는 최종 승인 0이므로 차단; B 가중치 동결·step-matched 비교는 계획만 존재|
|정상 오탐·희소 유형 평가|부분 구현|PR35 metrics/diagnostics 존재. 독립 32/40대화·정답 미확보. 모델 우월성이나 현장 일반화 주장은 불가|
|TRAIN 권한 및 2인 승인 게이트|부분 구현|`v2_pipeline_gate.approval_audit/prepare_partition`는 두 사람 최종합의+데이터 지문 결부 사용결정을 요구. v1 권한·독립 gold와 향후 인간 작성 데이터 스키마 통합은 추가 필요|
|체크포인트 출력 보호|부분 구현|`experiment_runtime.output_path/reserve_output`는 전용 경로·run 중복·경로 이탈 거부. 실제 미래 trainer의 writer 전체 연결과 expanded metadata는 미구현|
|원본 추진안 양성 목표/성능 합격 기준|확인 불가|원문 미확보. 신규 문서의 목표는 이번 설계 제안이며 원문 수치로 표시하지 않음|

기존 readiness 문서의 “v1 입력·체크포인트 미확보”는 과거 시점 기록이다. 입력은 이미 원격 v2에서 복구돼 있고, 체크포인트는 이번 PC에서 추가 확인됐다. 원본 보고서를 덮어써 과거 이력을 바꾸지 않는다. 새 프로토콜의 `original_v1_checkpoint_restored=false`는 해당 실험에 과거 가중치를 로드하지 않는다는 뜻이며, 로컬 파일이 없다는 뜻이 아니다.

## 검증 해석

모든 기존 tracked 파일을 시작 시 SHA-256으로 기록했다. 복구 데이터, 검수 CSV, 고정 PR35 소스, 기존 A/B/C와 보고서 보존은 전후 비교로 확인한다. 로컬 v1 두 체크포인트와 공개 가중치도 전후 해시를 비교한다. 가중치는 Git에 추가하지 않는다.

`unittest discover -s tests` 단일 프로세스 실행은 83개 실행 중 `Unexpected training module loaded` 오류 1건을 냈다. 서로 다른 고정 PR 스냅샷이 같은 `risk_speech_ai` 모듈명으로 로드되기 때문이다. 원본 코드를 변경하지 않고 기존 `reports/v2_publish/test_results.json`과 같은 파일별 프로세스 격리 방식으로 재검증한다. `tests.json`에는 기존 8개 suite, 신규 contract suite, PR35의 5개 데이터·입력·지표 suite 결과를 보존한다. 테스트 통과는 학습 승인·TEST 평가·모델 성능 통과를 뜻하지 않는다.

## 남은 차단 조건과 착수 판단

2차 코드 구현은 이 프로토콜과 의존성 목록을 기준으로 착수 가능하다. 실제 학습은 v1 사용권한 재확인, 데이터별 최종 검수·사용 승인, 신규 TRAIN/독립 VALIDATION 확보, TEST 담당자 봉인 영수증, 향후 trainer/evaluator 구현 완료 전까지 차단한다. 과거 v1 학습 자료는 그 과거 모델의 독립 TEST가 될 수 없다. 발견한 v1 가중치의 평가도 이번 범위에 포함하지 않는다.
