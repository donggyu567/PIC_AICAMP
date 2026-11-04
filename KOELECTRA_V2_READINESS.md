# KoELECTRA v2 pilot readiness

현재 상태는 **임정윤 1인 검수 완료 TRAIN 후보**입니다. 김해린의 독립 검수와 2인 최종 합의는 미승인입니다. 이 변경은 기존 승인 정책을 바꾸지 않으며 실제 모델 학습이나 v1 체크포인트 변경을 포함하지 않습니다.

- 정본: `dataset/04. processed/v2_pilot/pilot_canonical.jsonl`
- 실제 검수 기록: `dataset/review/v2_pilot/human_review_working.csv`
- 승인 입력 이력: `reports/v2_pilot/review_entries/`
- 1인 후보 및 별도 변환 결과: `dataset/04. processed/v2_pilot/training_candidate/`
- 최신 환경·실제 실행 결과: [ML runtime report](reports/v2_pilot/ml_runtime/README.md)
- 검증용 pinned Git 코드: `artifacts/v1_reference/` (원래 v1 파일을 수정한 것이 아닌 별도 스냅샷)

실제 CPU DataLoader는 136발화를 batch size 4로 처리해 34개 배치를 생성했습니다. 첫 배치 입력은 `[4,83]` int64, 이진/유형 라벨은 `[4,1]`/`[4,8]` float32입니다. 이전 최대 5발화, 8종 라벨 순서, TRAIN 전용 범위를 검증했습니다. 무작위 초기화 기본 모델의 forward 검증을 실제 v1 가중치 검증과 구분합니다.

실제 v1 prepared 입력·체크포인트는 아직 로컬에서 발견하지 못했습니다. 문서상 경로와 대조용 해시는 최신 ML 보고서에 있으며, 이 때문에 실제 v1 데이터와의 중복·독립 평가 비교가 완료됐다고 주장하지 않습니다.

## 재실행

프로젝트 전용 Python 3.12 환경에서 `torch==2.6.0`을 공식 CPU 인덱스로, `transformers==4.57.6`을 PyPI로 설치합니다. 전체 실제 설치 버전은 `reports/v2_pilot/ml_runtime/requirements-lock.txt`에 있습니다. 환경과 모델 캐시는 Git에 포함하지 않습니다.

```powershell
python -m venv .venv-v2
& '.venv-v2/Scripts/python.exe' -m pip install --index-url https://download.pytorch.org/whl/cpu 'torch==2.6.0'
& '.venv-v2/Scripts/python.exe' -m pip install --index-url https://pypi.org/simple 'transformers==4.57.6'
& '.venv-v2/Scripts/python.exe' -B -X utf8 dataset/scripts/cache_v2_tokenizer.py
& '.venv-v2/Scripts/python.exe' -B -X utf8 dataset/scripts/validate_v2_real_minibatch.py --random-forward
& '.venv-v2/Scripts/python.exe' -B -X utf8 -m unittest discover -s tests -p 'test_*.py' -v
```

이 명령들은 모델을 학습하지 않습니다. tokenizer/config만 내려받으며 v1 가중치를 포함하지 않습니다. `--random-forward`는 학습되지 않은 구조의 검증이며 checkpoint 저장·optimizer 실행을 하지 않습니다.

## 기록 해석과 커밋 범위

`reports/v2_pilot/`에는 초기 복원, 검수표 준비, 승인 입력, 샘플 연결, ML 실행의 단계별 기록을 보존했습니다. 초기 보고서의 미승인/의존성 부재 수치는 그 단계의 기록이며, 현재 검수 상태는 작업용 CSV와 승인 입력 이력, 현재 실행 상태는 `ml_runtime/`을 기준으로 봅니다. 파일에 기록된 과거의 "Git push 미수행"도 해당 작업 단계의 상태입니다.

커밋 대상과 검사는 `reports/v2_pilot/git_delivery_manifest.json`에 기록합니다. 3개 합성 TXT 출처, 검수자명·승인 기록, 사용자가 제공한 작업 경로는 재현·감사를 위한 작업 자료입니다. 실제 통화 원문·모델 가중치·비밀키·가상환경·캐시는 이번 변경에 추가하지 않습니다. 관계없는 개인 연구 문서와 빈 승인 중간 산출물도 제외합니다.
