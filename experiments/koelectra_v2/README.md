# KoELECTRA A/B/C 실험 구성 — preflight 전용

이 폴더는 새 `v1_retrained_baseline`과 설정/합성 증강 비교의 계획·후보 manifest·검증 도구입니다. **실제 학습 기능은 실행하지 않으며 `--train` 옵션도 제공하지 않습니다.** 기존 PR35 코드·복구 입력·정본·검수표를 수정하지 않습니다.

```powershell
# 기존 .venv-v2 사용. 일반 sandbox에서 아래 검증은 오프라인 실행 가능.
& '.venv-v2/Scripts/python.exe' -B -X utf8 experiments/koelectra_v2/plan_splits.py
& '.venv-v2/Scripts/python.exe' -B -X utf8 experiments/koelectra_v2/write_configs.py
& '.venv-v2/Scripts/python.exe' -B -X utf8 experiments/koelectra_v2/prioritize_reviews.py
& '.venv-v2/Scripts/python.exe' -B -X utf8 experiments/koelectra_v2/experiment_runtime.py --config experiments/koelectra_v2/configs/A.json --load-public-base
& '.venv-v2/Scripts/python.exe' -B -X utf8 experiments/koelectra_v2/experiment_runtime.py --config experiments/koelectra_v2/configs/B.json
& '.venv-v2/Scripts/python.exe' -B -X utf8 experiments/koelectra_v2/experiment_runtime.py --config experiments/koelectra_v2/configs/C.json
& '.venv-v2/Scripts/python.exe' -B -X utf8 -m unittest discover -s tests -p test_koelectra_experiment_design.py -v
```

C의 결과는 현재 `BLOCKED_EXPECTED_NO_APPROVED_SYNTHETIC`가 정상입니다. 전체 v1 후보를 A/B에서 각 split별 실제 DataLoader로 처리하지만, DRAFT split·미검수 평가 라벨이 승인되었다는 의미는 아닙니다. 현재 C는 미승인 208개를 넣지도, 조용히 빼고 B와 같은 실험으로 실행하지도 않습니다.

`prepare_public_base.py --download`는 공개 KoELECTRA 고정 revision의 encoder·tokenizer만 별도 `artifacts/v2_experiment_assets/` 캐시에 내려받고 해시를 검증합니다. 네트워크가 필요한 이 준비는 이미 성공했습니다. 과거 v1 분류기·optimizer 상태를 복원하지 않습니다. 나머지 실행은 같은 캐시를 offline mode로 사용합니다.

설정·split·손실 가중치 파일의 SHA가 맞지 않으면 중단합니다. 출력 후보 경로는 `artifacts/v2_comparison_runs/{experiment_id}/seed_{seed}/{run_id}/model.pt`이며, 실제 학습을 구현할 때 `reserve_output`으로 새 디렉터리를 원자적으로 예약해야 합니다. 기존 디렉터리 재사용·경로 탈출·v1 출력 루트·미등록 seed를 거부하는 테스트를 포함합니다. 이번 preflight는 예정 경로만 검사하고 task checkpoint를 쓰지 않습니다.

`loss_values`는 B/C의 계획된 weighted BCE 계산만 제공하고 optimizer/backward를 호출하지 않습니다. 기존 PR35 trainer에 이 함수를 자동 주입하거나 기존 in-sample evaluator를 holdout evaluator로 바꾸지는 않았습니다. 실제 학습 전 그 연결과 독립 출력·평가 경로의 별도 구현/검증이 남아 있습니다.

전체 계획·확인 사실·사람 검토 항목은 [실험 설계 보고서](../../reports/v2_experiment_design/README.md)를 참조하세요. 스크립트 재실행은 이 작업에서 생성한 draft 설정·보고서를 갱신하므로 사람 검토 이후에는 새 protocol version으로 분기하고 이미 봉인한 TEST/설정 파일을 덮어쓰면 안 됩니다.
