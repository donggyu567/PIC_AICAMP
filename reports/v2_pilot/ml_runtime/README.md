# ML 실행 환경·실제 미니배치·v1 자산 확인

**실제 PyTorch DataLoader 미니배치 검증을 완료했습니다.** 16대화·136발화를 batch size 4로 로딩해 34개 배치를 만들었습니다. 이는 과거의 샘플 생성기만 검증한 결과를 넘어선 이번 실행 결과입니다. 기존 보고서의 torch 부재 차단 상태는 이번 전용 환경에서 해결됐습니다.

## A. ML 실행 환경

| 항목 | 실제 값 |
|---|---|
| Python | 3.12.14, Windows AMD64 |
| 실행 파일 | `C:\Users\임정윤\OneDrive\Desktop\PIC_AICAMP\.venv-v2\Scripts\python.exe` |
| 전용 가상환경 | 프로젝트의 `.venv-v2/`, system-site-packages=false |
| 기본 Python | `C:\Users\임정윤\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe` (패키지 변경 없음) |
| torch | 2.6.0+cpu |
| transformers | 4.57.6 |
| tokenizers / huggingface_hub | 0.22.2 / 0.36.2 |
| numpy / safetensors | 2.5.4 / 0.8.0 |
| CPU / CUDA | CPU 실제 실행 성공 / CUDA 사용 가능 false, CUDA device count 0, CPU 전용 torch build |
| 의존성 검사 | `pip check`: No broken requirements found |

설치 근거는 PR35의 고정 커밋 `9bab7e383928426e2d866de90acae013fe1f7d86`의 `requirements-ai.txt`입니다. 해당 명세는 torch==2.6.0, transformers==4.57.6이며 주석의 Python 3.11과 달리 이번에는 3.12.14에서 실제 동작을 검증했습니다. torch는 공식 CPU 인덱스, transformers와 필수 하위 의존성은 PyPI에서 전용 환경에 설치했습니다. 전체 설치 버전은 `requirements-lock.txt`에 있습니다. 코드에서 Hugging Face `datasets`를 사용하지 않아 설치하지 않았습니다. GPU 하드웨어 자체의 부재를 단정하지 않으며, 이번 실행환경은 CPU 전용입니다.

기본 샌드박스에서 외부 소켓이 WinError 10013으로 차단되는 것을 확인한 후, 허용된 네트워크 실행으로 다운로드·설치를 완료했습니다. 이전 `No matching distribution found`를 현재 환경의 설치 불가능으로 해석하지 않습니다. 전용 환경 밖의 Python 패키지는 변경하지 않았습니다.

토크나이저는 공개 `monologg/koelectra-base-v3-discriminator`의 PR35 고정 revision `68b30cd259f34a4b5aa8786392612ba2a2617fcc`를 사용했습니다. 프로젝트의 `artifacts/v2_runtime_assets/hf/`에 config·tokenizer_config·vocab 3개만 내려받았고 모델 가중치는 다운로드하지 않았습니다. 어휘 지문은 PR35 재현성 보고서의 값과 대조했습니다. 파일 해시는 `tokenizer_cache.json`, 실제 토크나이저 metadata는 `real_minibatch_result.json`에 있습니다.

## B. 실제 DataLoader 검증

검증 코드: `dataset/scripts/validate_v2_real_minibatch.py`. 기존 PR35의 `build_safe_training_samples`, `load_koelectra_tokenizer`, `RiskSpeechDataset`, `DynamicPaddingCollator`, `make_training_dataloader`를 실제로 사용했습니다. 테스트 토크나이저나 DataLoader 대체 구현은 사용하지 않았습니다.

| 검증 항목 | 실제 결과 |
|---|---|
| 데이터 | 16대화·136발화, 원래 구조·순서·ID·내용·라벨 일치 |
| 샘플 | 136개, 제외·잘못된 라벨 0 |
| 문맥 | 136개 전체에 대해 동일 대화의 이전 최대 5발화 일치 |
| 입력 token 길이 | 20~160; 길이 제한으로 제거한 문맥 0 |
| 실제 DataLoader | torch.utils.data.DataLoader, batch size 4, 34개 배치 |
| 입력 3종 | 첫 배치 input_ids·attention_mask·token_type_ids 각각 [4,83], torch.int64, CPU |
| 위험 여부 라벨 | [4,1], torch.float32, CPU; 전체 피싱 34·정상 102 |
| 위험 유형 라벨 | [4,8], torch.float32, CPU; 전체 37 Positive |
| 위험 유형 순서 | institution_impersonation, money_transfer, personal_information, app_installation, secrecy, threat_pressure, loan_fraud, information_probing |
| 배치 전체 검사 | 34개 모두 shape·dtype·실제 token IDs·mask·패딩·타깃 일치 |
| 분할 | 후보와 어댑터 모두 train, validation/test 유입 0 |
| 기존 학습 CLI | `--train` 없이 validation-only 실제 실행 성공 |
| 실제 검증 항목 | 16개 통과, 실패 0 |
| PR35 비학습 테스트 | 48개 통과, 실패·오류·생략 0 |

48개 원본 테스트는 training_data·tokenization·dataset·metrics·splits 범위입니다. optimizer를 실행하는 원본 학습 integration test는 수행하지 않았습니다. 상세 기계 판독 결과는 `real_minibatch_result.json`에 있습니다.

추가로 **실제 기본 KoELECTRA 구조를 무작위 가중치로 초기화**해 기존 RiskSpeechClassifier의 순전파를 CPU inference_mode로 실행했습니다. 파라미터 수 112,337,673, risk logits [4,1], type logits [4,8], 유한값 검사 통과입니다. gradient·backward·optimizer step·체크포인트 저장은 0입니다. **학습된 v1 체크포인트를 로딩한 검증이나 성능 평가가 아닙니다.** 무작위 모델의 출력값으로 정확도·F1을 보고하지 않았습니다.

## C. v1 자산 목록

출처는 [PR #35](https://github.com/donggyu567/PIC_AICAMP/pull/35)와 그 head `9bab7e383928426e2d866de90acae013fe1f7d86`입니다. 확인 당시 PR은 open·미병합 상태였습니다. PR의 구현은 현재 로컬 브랜치에 없었으므로 **별도 `artifacts/v1_reference/pr35_9bab7e383928/`에 복원**했습니다. 28개 파일을 Git blob과 SHA-256으로 대조했습니다. 기존 `risk_speech_ai/`와 이전 스냅샷은 덮어쓰지 않았습니다.

아래 `PR35/`는 `C:\Users\임정윤\OneDrive\Desktop\PIC_AICAMP\artifacts\v1_reference\pr35_9bab7e383928\`입니다. 전체 절대경로·해시·검증은 `v1_asset_inventory.json`에 있습니다.

| 자산 | 실제 경로 또는 문서상 위치 | 분류 / 상태 |
|---|---|---|
| 모델 정의 | PR35/risk_speech_ai/model.py | Git 복원 완료·실제 순전파 가능 |
| 학습 코드·CLI | PR35/risk_speech_ai/training.py, train_cli.py | Git 복원 완료·검증 모드 실행 가능, 학습은 미실행 |
| 데이터 로더 | PR35/risk_speech_ai/dataset.py, training_data.py | 실제 DataLoader 실행 가능 |
| 토크나이저 | PR35/risk_speech_ai/tokenization.py + artifacts/v2_runtime_assets/hf/ | 실제 실행 가능 |
| 평가 코드 | PR35/risk_speech_ai/metrics.py, evaluate_cli.py | Git 복원 완료·지표 테스트 통과, 실제 가중치 평가 미실행 |
| v1 학습 입력 | 문서상 artifacts/risk_speech_ai/prepared/labels.jsonl, tuned.jsonl | **현재 파일 미발견**, Git ignore 대상 |
| v1 체크포인트 | 문서상 artifacts/risk_speech_ai/koelectra_risk_v1.pt, checkpoints/risk_speech_v1.pt | **현재 파일 미발견**, PR/Git LFS에 위험감지 가중치 없음 |
| TRAIN/VALIDATION/TEST 분할 | 실제 독립 분할 manifest 미발견 | PR35는 TRAIN IN-SAMPLE 평가라고 명시, 독립 validation/test는 준비되지 않은 상태로 기록됨 |
| 향후 split 계획 코드 | PR35/risk_speech_ai/splits.py | 참고용 계획 구현, 기존 실험의 분할 정보가 아님 |
| 과거 사용 결정 manifest | PR35/risk_speech_ai/data_review_manifest_20261027.json | 참고용 근거, 실제 prepared 파일과 구별 |

PR35가 보고한 원본 데이터 commit은 `8faa6a7eebfe95c7ac7fe6c6077a49ebf31f958f`이며 현재 로컬 Git에는 그 객체가 없습니다. 현재 raw·masked 자료를 실제 v1 학습 입력이라고 간주하지 않았습니다. 원본 prepared 파일을 수령한 뒤 아래 해시와 비교해야 합니다.

- labels.jsonl: `c205049e1aa2125ad40cc6cea1465b2c2793cc7fedf02b7eab8e1d9f20e9c9e5`
- tuned.jsonl: `50ea88cc3ee9c3df1477082ab5daf82ef77f83329374b50f312874592462e6f2`
- v1 .pt: `1131f9dcc665f79073d98ecd6845573109a89e44dbf2917d299a8fea057020a7`, 1,348,308,730 bytes

위 값은 **PR35에 기록된 대조 기준이며 이번 PC에서 해당 원본 파일의 무결성을 확인한 결과가 아닙니다.** PR35는 실제 가중치 외부 전달이 완료되지 않았다고 기록합니다. 학습 당시 미커밋 코드의 정확한 snapshot도 기록되지 않았으므로 PR35 코드를 당시 학습 실행과 완전히 동일하다고 단정하지 않습니다.

프로젝트·로컬 브랜치·Git 이력·worktree·LFS 목록·접근 가능한 관련 Downloads/문서/Codex 경로·기본 HF 캐시를 확인했습니다. Git LFS에는 Android STT와 KoELECTRA PII NER ONNX 등이 있지만 위험감지 v1의 두 head를 가진 .pt가 아니므로 대신 사용하지 않았습니다. 전체 PC·다른 사람의 PC를 모두 검색했다고 주장하지 않습니다.

## D. 다음 단계 판단

**v2 후보는 PR35의 실제 학습 입력·DataLoader 경로에 연결 가능합니다.** 이번 범위는 1인 검수 후보의 실행 호환성 확인이며, 실제 학습 시작 승인이나 기존 2인 최종 승인 정책 변경이 아닙니다. 김해린·최종 합의는 그대로 미승인이고 CSV·정본·후보·기존 승인 JSONL을 보존했습니다.

실제 학습·공정 비교 전 남은 일:

1. v1 prepared 입력과 체크포인트를 문서상 인계 위치에서 확보하고 위 해시를 대조합니다. 실제 학습 입력이 있어야 v2와 완전 일치·정규화·유사 중복 및 출처/가족 충돌 검사를 완료할 수 있습니다.
2. v1과 v2의 학습에 들어가지 않은 새 대화·원자료로 독립 validation/test를 마련하고 분할을 고정합니다. 이미 v1이 학습한 자료를 나중에 나눠 독립 평가 데이터라고 부르지 않습니다. 이번에는 어떤 데이터도 validation/test로 생성·재분류하지 않았습니다.
3. 같은 라벨 순서·문맥 최대 5개·토큰 길이·전처리 조건의 동일 고정 test로 v1/v2를 평가합니다. 임계값 선택은 validation에서 하고 test를 튜닝에 사용하지 않습니다. PR35의 기존 지표는 TRAIN IN-SAMPLE이며 이번 실행에서 재측정한 독립 성능이 아닙니다.
4. 기존 정책의 독립 검수·최종 합의와 학습 사용 결정을 별도로 마무리하고, 기존 v1 체크포인트를 덮어쓰지 않는 v2 실험 경로를 정합니다. 체크포인트가 확보되면 먼저 실제 v1 로딩·추론 검증을 진행합니다.

## 재실행

```powershell
# 이미 준비한 프로젝트 전용 환경과 캐시로 오프라인 실행; 학습하지 않음
& '.venv-v2/Scripts/python.exe' -B -X utf8 dataset/scripts/validate_v2_real_minibatch.py --random-forward
& '.venv-v2/Scripts/python.exe' -B -X utf8 dataset/scripts/report_v2_ml_assets.py
```

첫 명령의 `--random-forward`는 모델 구조의 무작위 초기화 순전파만 추가하며, 옵션을 빼면 실제 DataLoader 검증까지만 실행합니다. 모델 학습·기존 체크포인트 변경·정본/검수 결과 수정·Git push·PR 생성은 수행하지 않았습니다.
