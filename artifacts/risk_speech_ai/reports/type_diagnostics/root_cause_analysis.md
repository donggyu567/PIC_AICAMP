# 위험 유형 F1=0 원인 분석

**TRAIN (IN-SAMPLE), 1,460발화.** 체크포인트 schema v1과 기본 임계값 0.5는 그대로 유지했다.

## 직접 원인과 구분력

모든 유형의 관측 최대 예측 확률이 .286 이하다. 따라서 0.5 기준 양성 예측은 8개 유형에서 모두 0건이며 TP=FP=0, Recall=F1=0이다. 이는 확률을 추가로 sigmoid 처리하거나 100점 변환을 중복 적용한 결과가 아니다. [inference.py](../../../../risk_speech_ai/inference.py)의 `logits_to_outputs()`가 raw logits에 sigmoid를 한 번 적용하고, 별도의 0~100 점수 필드를 만든다.

출력이 상수인 것은 아니다. 전체 표준편차는 유형별 .0146~.0311이고, `loan_fraud`와 `institution_impersonation`의 TRAIN ROC-AUC는 각각 .880, .817이다. 그러나 `personal_information` .523, `app_installation` .548은 약한 순위 신호이며, 낮은 임계값에서 대량 오탐이 발생한다. 학습 데이터에서 관측한 AUC와 임계값 F1은 일반화 성능을 보장하지 않는다.

## 구현 검증

- [labels.py](../../../../risk_speech_ai/labels.py)의 8개 정규 순서를 `to_multi_hot()`이 사용한다. [training_data.py](../../../../risk_speech_ai/training_data.py)의 `_targets()`가 이를 `type_targets`에 넣고, [dataset.py](../../../../risk_speech_ai/dataset.py)가 8차원 float target을 만든다.
- [model.py](../../../../risk_speech_ai/model.py)의 `type_classifier`는 encoder CLS 표현에서 8개의 raw logit을 만든다. [training.py](../../../../risk_speech_ai/training.py)의 `compute_losses()`는 `BCEWithLogitsLoss(reduction="mean")`를 유형과 피싱 head에 각각 적용한 뒤 기본 가중치 1.0으로 합친다. 학습 루프가 합산 손실을 역전파하고 AdamW optimizer step을 실행한다.
- 기존 `tests/test_training.py`의 gradient 검사는 유형 loss가 유형 head와 공유 encoder까지 도달함을 확인한다. `tests/test_checkpoint_compatibility.py`는 유형 head shape와 state_dict 복원을 확인한다. 실제 checkpoint의 유형 head weight/bias shape은 `(8, 768)`/`(8,)`이고 optimizer 상태의 마지막 네 파라미터(risk/type head)는 각각 step 183을 기록한다. 이번 실제 체크포인트의 재로딩과 1,460개 추론도 성공했고, 유형별 확률이 발화에 따라 달랐다. 코드 경로와 실제 재로딩에서 유형 head의 미연결 또는 중복 sigmoid 오류는 발견하지 못했다.
- 기존 학습 기록은 **1 epoch, 183 optimizer steps**이며 평균 total/risk/type loss는 .870836/.562352/.308484다. 현재 기록만으로 각 유형의 학습 기여도 또는 독립 데이터 성능을 따로 확정할 수 없다.

## 불균형과 제한된 학습

8개 출력에 대해 양성은 총 571/11,680 (4.89%)이다. 유형별 음성:양성 비율은 순서대로 7.30, 15.22, 44.63, 242.33, 68.52, 17.02, 21.46, 13.60이다. 현재 유형 BCE는 양성 가중치가 없고 모든 출력 요소를 평균하므로 각 희소 양성의 기여가 많은 음성에 비해 작다. 이는 확률이 낮은 구간에 모인 현상과 부합하지만, 불균형만이 유일 원인이라고 증명하는 실험은 이번에 하지 않았다. 1 epoch와 라벨 잡음·입력 전처리 차이도 영향을 줄 수 있다.

특히 `app_installation`은 양성 6건뿐이다. `pos_weight=N/P`를 그대로 쓰면 242.33으로 학습이 불안정할 수 있다. 새 데이터 확보 없이 해당 유형의 효과를 주장할 수 없다.

## 백엔드 연동 위험

확인한 백엔드 기준은 `origin/feature/backend` commit `4502ffa9bdb2039b529d338f5d51f155d041aae2`다. 이 브랜치의 `RiskAnalyzer`는 0~1 `is_phishing_score`, 8개 `type_scores`, `detected_types`를 받는다. 빈 유형 목록은 유효하다. `calculate_risk()`는 **전체 피싱 확률만**으로 최근 최대 및 누적 위험을 계산하므로 빈 유형 목록이 위험 점수를 0으로 만들지 않는다. 기본 `DefaultWarningPolicy`는 점수가 70/100 이상이면 경고를 활성화하며 유형 목록을 조건으로 삼지 않는다. 따라서 점수가 충분히 높으면 유형 미감지 상태에서도 일반 경고가 가능하다.

반면 근거의 `risk_types`는 빈 목록으로 전달되어 유형별 설명이 빠진다. 전체 위험 점수가 경고 기준에 도달하지 않으면 유형별 확률만으로 경고를 보완하지 못한다. `RiskAnalyzer`는 인터페이스이며 실제 checkpoint 어댑터의 서비스 연결 여부는 이 확인으로 검증되지 않았다. 연동 시 AI의 `risk_probability`와 `type_probabilities`를 0~1 점수에 사용하고 `detected_types`를 그대로 전달해야 한다. AI의 `risk_score`와 `type_scores`는 0~100 표시용이다.

현재 .pt는 전체 피싱 점수를 내는 데 사용할 수 있으나, 기본 임계값으로 **8개 유형을 식별하는 기능은 관측된 학습 집합에서 작동하지 않았다**. 실제 서비스 입력은 LLM 보정된 `tuned_text`일 수 있고 학습에는 검증된 마스킹 원문을 사용했으므로, 서비스 성능은 별도 검증이 필요하다.
