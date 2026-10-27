# 후속 학습 개선 계획

현재 체크포인트는 변경하지 않았다. 아래의 임계값과 가중치는 향후 학습·검증 실험안이며 확정된 배포 설정이 아니다.

## 우선순위 3개

1. **새 대화와 가능하면 새 원자료를 확보하고 먼저 분리한다.** 기존 68개 대화, 1,460발화는 이미 checkpoint 학습에 노출됐다. 나중에 분할해도 이 checkpoint의 독립 TEST가 아니다. 출처 ID와 대화 ID를 묶어 중복 원문·유사 대화 누출을 검사하고, 라벨과 사용권·사람 검수 상태를 보존한다. 새 데이터에서 train/validation/test를 사전에 분리하고 희소 라벨의 양성이 validation/test에도 충분히 있는지 점검한다. `app_installation`은 현재 양성 6건이므로 특히 추가 확보가 선행되어야 한다.
2. **향후 재학습에서 양성 희소성을 직접 다루는 loss를 검증한다.** 첫 실험은 train 부분에서만 계산한 유형별 `BCEWithLogitsLoss(pos_weight=...)`다. 비율 원값(최대 242.33)을 그대로 쓰지 말고 smoothing 또는 상한을 사전에 정해 validation precision/recall 및 calibration을 확인한다. 기존 BCE를 기준선으로 남기고 변경점은 독립 실행으로 기록한다.
3. **validation으로 epoch와 임계값을 고르고 test는 한 번만 평가한다.** 1 epoch 기준선과 추가 epoch를 비교하고 validation loss·유형별 PR-AUC·F1·오탐을 함께 본다. 필요한 경우 유형별 임계값을 validation에서만 선택하고 버전으로 관리한다. test 결과에 맞춰 사후 조정하지 않는다.

## 대안 비교

| 방법 | 기대 효과 | 비용·위험 | 판단 |
| --- | --- | --- | --- |
| Positive class weighting (`pos_weight`) | 희소 양성의 gradient를 직접 높임 | 매우 희소한 유형에서 과도한 가중치와 오탐 증가 | **새 train/validation split 후 첫 loss 실험** |
| Focal Loss | 쉬운 음성의 영향 감소 | alpha/gamma 튜닝, 확률 보정 악화 가능, 희소 양성 소표본 문제 지속 | weighted BCE로 부족할 때 비교 |
| 유형 loss 전체 가중치 | 피싱 head보다 유형 head의 학습 비중 증가 | 유형 내부의 양성:음성 불균형은 그대로 | 단독 해법보다 보조 실험 |
| Epoch 증가 | 아직 덜 학습된 구분 신호 개선 가능 | 라벨 잡음 과적합과 시간 증가 | validation 조기 종료와 함께 검증 |
| 라벨별 추가 데이터 | 희소 유형의 일반화 가능성 개선 | 수집·사용권·라벨 검수 비용 | **필수**, 특히 `app_installation` |
| validation 기반 유형별 임계값 | 순위 신호가 있는 유형의 탐지율 조정 | 낮은 임계값에서 FP 증가, 학습 집합 최적화 편향 | 새 validation 확보 후에만 적용 |

## 독립 평가 설계

- 기존 1,460발화와 동일·유사한 텍스트 및 원자료를 새 test에서 제외한다. 새 데이터의 출처, 데이터 버전, split seed, 대화 단위 배정표와 중복 검사 결과를 남긴다.
- 단일 대화의 모든 발화를 같은 split에 두고, 가능한 경우 같은 원자료에서 파생된 여러 대화도 같은 split에 둔다. 출처별 holdout을 우선 검토한다.
- train에서 가중치와 모델을 학습하고, validation에서 epoch·loss 설정·임계값을 고른다. test는 그 뒤 한 번만 최종 평가한다. 유형별 support, ROC-AUC, AP, precision/recall/F1과 전체 피싱 성능을 모두 보고한다.
- 학습과 백엔드 추론의 입력 전처리 차이(학습은 마스킹 원문, 서비스는 LLM 보정 가능)를 같은 test 대화에서 측정한다. 원문과 개인정보를 결과 보고서에 넣지 않는다.
