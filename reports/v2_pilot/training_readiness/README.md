# KoELECTRA v2 1인 검수 후보와 기존 파이프라인 연결

임정윤의 승인 136행을 확인한 **1인 검수 완료 TRAIN 후보**를 생성했습니다. 김해린은 136행 미승인, 최종 합의도 136행 미승인입니다. 기존 2인 최종 승인 정책을 바꾸지 않았고 최종 승인 JSONL은 갱신하지 않았습니다.

## 후보와 실제 실행 결과

| 항목 | 결과 |
|---|---|
| 후보 | 16대화·136발화, 전부 train·합성 |
| 피싱 / 정상 | 34 / 102 |
| 유형별 Positive | 기관 사칭 10, 금전 이전 3, 개인정보 4, 앱 설치 7, 비밀 유지 5, 위협·압박 3, 대출 사기 3, 정보 탐색 2. 합계 37 |
| 기존 샘플 생성기 실행 | 136개 포함, 제외·중복 ID·누락·잘못된 라벨 0 |
| 문맥 검사 | 136개 타깃 모두 원본 순서·현재 발화·이전 최대 5발화 일치 |
| 기존 코드 계약 테스트 | 39개 중 38개 통과, transformers가 필요한 1개는 의존성 부재로 생략 |
| 새 변환기 테스트 | 6개 통과 |
| 실제 DataLoader 미니배치 | 실행 차단: torch 없음. 실제 토크나이저·모델 forward·배치 tensor shape는 미검증 |
| 모델 학습 / optimizer step | 미실행 / 0 |
| 실제 v1 학습 데이터 중복 검사 | 실제 입력 파일을 찾지 못해 미완료 |

초기 전체 테스트 시도에서는 의존성 없는 1개 테스트가 오류로 기록됐습니다. 원본 테스트 파일은 수정하지 않고 실행기에서 해당 테스트만 명시적으로 생략하도록 처리했습니다. 초기 기록은 `execution_initial_attempt.json`, 최종 실제 실행 기록은 `execution_result.json`입니다. 계약 테스트의 테스트 토크나이저 결과를 실제 KoELECTRA 토크나이저 검증으로 보고하지 않습니다.

## 파일

- 후보: `dataset/04. processed/v2_pilot/training_candidate/pilot_single_review_train_candidate.jsonl`
- 기존 로더용 라벨: 같은 폴더의 `v1_adapter_label_candidates.jsonl`
- 기존 로더용 입력 텍스트: `v1_adapter_text_candidates.jsonl`
- 실제 샘플 생성기 출력: `v1_adapter_sample_candidates.jsonl`
- 대화 출처·생성·수정·검수 이력: 후보 원본 및 `conversation_provenance.jsonl`
- 변환·검증 코드: `dataset/scripts/prepare_v2_training_candidate.py`
- 학습 없는 실행 점검: `dataset/scripts/smoke_v2_training_candidate.py`
- 중복 보고서: `actual_v1_duplicate_report.json`, `reference_duplicate_report.json`
- 데이터 검증 및 해시: `preparation_result.json`, `context_audit.json`

대화 단위 후보는 기존 정본의 각 객체와 발화 배열을 그대로 복사하고 `review_preparation`만 추가했습니다. 기존 `review_status=generated`, generation_model, revision_history, source_kind, actual_call, scenario_family_id를 보존합니다. 1인 승인과 최종 승인은 서로 다른 상태입니다. 실제 과거 검수 시각은 미상으로 유지하고, 이전 승인 기록 시각은 출처 이력에서 별도로 인용했습니다.

## Git에서 복원한 구현

현재 체크아웃은 `data/dataset-v0.1-202609w4-jeongyun`이고 `risk_speech_ai/`는 비어 있습니다. 다른 로컬 브랜치 및 remote-tracking ref에서 구현을 찾았습니다.

- `feature/task3-risk-speech-ai`에는 예전 문맥 처리 코드가 있습니다.
- `origin/codex/backend-ai-integration` 및 `origin/feature/backend`에는 KoELECTRA 학습·추론 구현이 있습니다.
- 이번 연결은 `958c30e4ac6c43af015b1af75b295bfc1b6dfbcc` 커밋을 기준으로 합니다. 브랜치 전환·merge·fetch 없이 로컬 Git 객체를 읽었습니다.
- 별도 스냅샷: `artifacts/v1_reference/958c30e4ac6c/`. 원본 바이트·Git blob·SHA-256은 그 안의 `source_manifest.json`에 있습니다. 현재 브랜치의 `risk_speech_ai/`를 덮어쓰지 않았습니다.

| 기능 | 복원 파일 / 확인한 동작 |
|---|---|
| 모델 | model.py: monologg/koelectra-base-v3-discriminator의 공유 encoder, 위험 logit [B,1]과 유형 logit [B,8] |
| 라벨 | labels.py: 기존 가이드와 같은 8종 순서, multi-hot 변환 |
| 샘플 로더 | training_data.py: 라벨·tuned_text를 대화/발화 ID로 결합, 최대 5개 이전 발화 |
| 데이터셋 | dataset.py: RiskSpeechDataset, DynamicPaddingCollator, make_training_dataloader |
| 토크나이저 | tokenization.py: 문맥을 첫 segment, 현재 발화를 둘째 segment로 처리. 최대 512 tokens, 오래된 문맥부터 통째로 제거. 현재 발화 자체가 초과하면 오류 |
| 학습 | training.py: 두 BCEWithLogitsLoss, AdamW, 전체 encoder와 두 head 학습, 마지막 epoch 저장. 이번에는 호출하지 않음 |
| 평가·추론 | inference.py: sigmoid 위험 확률과 8종 확률·독립 threshold. 별도 validation/test 지표 평가 루프는 복원된 모듈에 없음 |
| 체크포인트 | checkpoint.py: schema v1, 모델·라벨 순서·토크나이저·문맥 계약 검증 후 로딩. 실제 학습 체크포인트 파일은 찾지 못해 로딩 미검증 |

이 스냅샷이 존재한다는 사실과 실제 v1 실험이 이 커밋으로 수행됐다는 사실은 다릅니다. run manifest·체크포인트 metadata가 없어 **실제 v1 학습 실행과의 코드/데이터 연결은 아직 확인하지 못했습니다.**

## 실제 데이터와 참고 데이터의 구분

현재 프로젝트, 로컬 Git 전체 ref 이력, 관련 Downloads 후보 디렉터리·파일명, 기본 Hugging Face 캐시에서 학습 입력·체크포인트를 탐색했습니다. 저장소의 체크포인트/모델 캐시는 Git ignore 대상이며, 실제 파일이 Git에 포함돼 있지 않습니다. 관련 원본 ZIP은 파일럿 소스 자료이고 실제 v1 TRAIN/VALIDATION/TEST 입력의 근거가 아닙니다. 전체 PC의 모든 경로를 검색한 것은 아닙니다.

`dataset/01. raw/`, `02. staging/`, `03. masked/`는 현재 확인 가능한 참고 원자료입니다. 797개 파일에서 발화 버전 1,281개·대화 버전 98개를 비교했습니다.

- 후보 ↔ 참고 데이터: 완전 일치 0, 정규화 일치 0, 고유사 발화(SequenceMatcher >=0.90) 0, 고유사 전체 대화(>=0.90) 0.
- 파일럿 내부: 0003-4 ↔ 0006-4 동일 문장 1그룹. 정상 발화이며 삭제하지 않고 후보로 보존했습니다.
- 정규화: NFKC·casefold 후 공백/문장부호 제거. 대화 유사도는 전체 발화 연결 문자열 기준입니다. 의미적으로 같은 시나리오인지까지 입증하는 검사는 아니며, 실제 v1 시나리오 자료가 없으므로 의미적 시나리오 중복은 미확인입니다.
- 실제 v1 입력·분할 manifest가 없어 TRAIN↔VALIDATION↔TEST 내용·가족 분할 충돌은 미검증입니다. 후보의 가족 16개는 서로 다르고 전부 train이지만, 이것만으로 전체 분할 누출이 없다고 결론내리지 않습니다.

확인에 필요한 것은 **실제 v1 학습에 사용한 라벨+tuned_text 입력 또는 sample JSONL, validation/test 입력과 split manifest, 실제 체크포인트와 실행 metadata의 저장 경로**입니다. 존재하지 않는 파일 이름을 실제 경로로 가정하지 않았습니다. 명시적 실제 입력이 제공되면 변환기 옵션 `--v1-train`, `--v1-validation`, `--v1-test`로 읽을 수 있습니다. nested utterances 또는 flat text/current_text/tuned_text 입력을 지원하고 split 표기가 인자와 다르면 거절합니다.

## 변환기의 연결 범위와 안전장치

기존 `build_training_samples(label_rows, tuned_rows)`에 맞춰 별도 파일로 변환했습니다. 텍스트는 정본과 동일하며 별도 LLM 교정은 하지 않았습니다. SYN2 ID와 발화 번호를 바꾸지 않습니다. 라벨 순서·멀티라벨·문맥은 기존 구현에서 실제로 검증했습니다.

기존 로더의 `label_status=reviewed`는 현재 타깃이 검수됐다는 내부 상태이며 2인 최종 승인 여부를 표현하지 않습니다. 따라서 어댑터에는 `--allow-single-review-candidate` 명시 옵션을 요구하고 모든 산출물에 `approval_stage=single_review_train_candidate`, `final_approved=false`를 보존합니다. 최종 승인·학습 병합 기능은 없습니다.

원본 로더는 라벨이 없는 tuned 발화도 문맥으로 사용할 수 있습니다. 이 때문에 어댑터가 **타깃과 tuned 문맥 모두 1인 승인된 동일 TRAIN 대화만 받도록** 선제 검증합니다. 미승인 문맥, validation/test 입력, 중복 대화, 순서 오류는 거절합니다. 기존 학습 코드는 수정하지 않았습니다.

## 실행 방법

저장소 루트의 PowerShell에서 사용 가능한 Python 실행 파일로 실행합니다. 이 환경의 Python은 PATH에 없으므로 아래 경로를 사용했습니다.

```powershell
& 'C:\Users\임정윤\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -B -X utf8 dataset/scripts/prepare_v2_training_candidate.py --allow-single-review-candidate
& 'C:\Users\임정윤\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -B -X utf8 dataset/scripts/smoke_v2_training_candidate.py
```

이 두 명령은 학습하지 않습니다. 두 번째 명령은 실제 패키지·캐시가 있을 때만 DataLoader 1개 배치를 생성하고, 없으면 차단 사유를 보고합니다. 테스트용 토크나이저를 실제 배치 검증에 대신 사용하지 않습니다. 원본 저장소의 optimizer-step integration test는 실행하지 않았습니다.

## 실제 학습 전 남은 문제

1. 실제 v1 train/validation/test 입력·split manifest·체크포인트와 해당 코드 커밋의 연결을 확인하고 중복·분할 누출을 다시 검사해야 합니다.
2. Windows/Python 3.11용 원본 의존성은 torch==2.6.0, transformers==4.57.6입니다. 현재 런타임은 Python 3.12.14이며 torch·transformers·tokenizers·huggingface_hub가 없습니다. 공식 CPU 인덱스 조회도 `No matching distribution found for torch`로 실패했습니다. 호환 ML 환경과 KoELECTRA 토크나이저/모델 자산을 마련한 후 실제 DataLoader 미니배치를 검증해야 합니다. 이 오류만으로 외부 네트워크나 모든 Python 환경의 설치 가능 여부를 단정하지 않습니다.
3. 실제 체크포인트 로딩 및 위험/유형 head 출력 shape·유한값을 학습 없이 검증해야 합니다. 현재 모델 forward 결과나 정확도는 없습니다.
4. 기존 정책에 따른 김해린의 독립 승인·최종 합의는 여전히 미완료입니다. 1인 후보 생성이 이 요건을 없애지 않습니다. 검수 기록 시각과 실제 과거 검수 시각도 구분한 상태로 유지합니다.

**샘플 생성기까지의 연결은 검증됐고 실제 학습 실행 준비는 미완료입니다.** 원본·검수 CSV·기존 최종 승인 JSONL은 SHA-256이 그대로이며, 모델 학습·체크포인트 변경·Git push·PR 생성은 수행하지 않았습니다.
