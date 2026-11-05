# A/B/C 공정 비교 프로토콜 — 학습 전 설계

프로토콜 버전은 `koelectra-comparison-design-20261106`입니다. 모든 수치 성능은 아직 미측정이며 아래 설정은 사전 등록 제안입니다. 공통 split·예외·평가 정답·학습 사용 결정이 미확정이므로 실제 학습은 차단 상태입니다.

|실험|정체성|학습 자료|설정의 차이|
|---|---|---|---|
|A|`v1_retrained_baseline`|공통 v1 TRAIN 후보 48대화·943발화|확인 가능한 과거 recipe: 무가중 이진+유형 BCE, 각 계수 1|
|B|`v2_loss_balanced` 개선 후보|A와 정확히 같은 자료·순서 정책·평가 자료|유형 BCE의 pos_weight만 변경; 그 외 조건 동일|
|C|`v2_approved_synthetic`|B와 같은 v1 TRAIN + 실제 승인된 합성 TRAIN만|B의 손실·가중치·LR·epoch·threshold·시드를 그대로 사용|

A는 과거 체크포인트를 복원한 모델이 아닙니다. B가 개선된 결과를 냈다는 주장도 아직 할 수 없습니다. C의 합성 자료는 현재 0개가 최종 승인됐으므로 학습 입력 구성 자체가 BLOCKED입니다. 미승인을 넣거나 C를 몰래 B와 같은 자료로 실행하지 않습니다.

## 공통 조건

- 같은 공개 KoELECTRA 고정 encoder revision과 tokenizer, 같은 이진/8유형 head, 같은 초기화 seed를 사용합니다. seed별로 A/B/C의 head 초기 상태를 맞춥니다.
- 같은 마스킹 원문, 문맥 5발화·최대 512토큰·현재 발화 보존·동적 패딩을 사용합니다. 전처리나 LLM 보정을 별도 차이로 넣지 않습니다.
- AdamW, LR 2e-5, weight decay .01, batch 8, epoch 1, CPU float32, num_workers 0, 계획 torch threads 2입니다. scheduler·early stopping은 넣지 않고 마지막 epoch를 선택합니다.
- split seed `20261106`은 고정하고, 학습 seed **42·43·44**를 모든 실험에 같은 세트로 사용합니다. 시드를 TEST 성능으로 선택하지 않습니다. 현재 세 시드 설정을 준비했으며 실제 학습 3회씩을 수행한 것은 아닙니다.
- 공통 v1 validation/test 후보만 주 비교에 사용합니다. 같은 사람 검수와 최종 gold version이 A/B/C에 모두 적용되어야 합니다.

## B의 사전 등록 변경

유형 l의 B 가중치는 원래 v1 **TRAIN만** 이용해 `min(5, sqrt(N_negative / N_positive))`로 계산하는 후보입니다. 양성 0이면 weight 1로 두고 해당 유형의 학습·평가 불가능성을 명시합니다. 루트·상한 5는 이번 설계의 고정 제안이며 성능으로 최적임을 확인한 값이 아닙니다.

[type_loss_weight_plan.json](../../experiments/koelectra_v2/type_loss_weight_plan.json)은 현재 TRAIN 후보 943개에서 구한 값과 입력·split 해시를 기록합니다. **C에서도 이 B 가중치 벡터를 재사용하고 합성 자료를 더한 분포로 다시 계산하지 않습니다.** 그래야 B→C에 손실 설정 변경이 끼어들지 않습니다. 분할이나 정답이 사람 검토로 바뀌면 실제 학습 전에 프로토콜 버전과 모든 arm의 가중치를 함께 재동결합니다.

이진 BCE는 무가중으로 유지합니다. shared encoder가 있으므로 유형 손실 변경은 이진 성능에도 영향을 줄 수 있으며 양쪽 지표를 모두 보고합니다. `experiment_runtime.loss_values`에 이 손실 경로를 구현했고 작은 fixture의 값·B/C 일치·gradient 미생성을 테스트했습니다. 실제 학습 loop에 이를 연결하는 작업은 학습 시작 승인 후에 해야 하며 원래 PR35 `compute_losses`가 이미 가중 BCE를 지원한다고 표시하지 않습니다.

## 계산량에 대한 공정성

현재 A/B는 943발화·batch 8·1 epoch → **118 updates** 계획입니다. 208개 전부가 나중에 승인되는 경우 C는 1,151발화 → **144 updates** 계획입니다. 현재 승인 0개이므로 C의 이 수치는 조건부 예상일 뿐입니다.

주 비교는 **같은 epoch·recipe**의 결과를 보고하되 C가 더 많은 optimizer updates를 얻는다는 사실을 함께 표시합니다. 따라서 B→C 차이를 합성 자료의 품질 효과만으로 단정하지 않습니다.

추가로 계산량 통제를 위해 **B_step_matched**를 사전 계획합니다. 승인된 실제 C 크기가 확정되면 C의 업데이트 수만큼 원래 TRAIN을 동일 seed·LR·손실로 반복하고, 정해진 step에서 정지합니다. 전부 승인될 때는 118+26=144 steps입니다. 이 예산은 TEST 점수가 아니라 최종 학습 자료 크기로만 결정합니다. 이 보조 비교를 실행할 미래 trainer에는 max-step·중단·새 checkpoint metadata 검증이 추가로 필요합니다. 이번에는 해당 학습도 실행하지 않았습니다.

## 평가 지표와 정의

이진 Precision/Recall/F1, ROC-AUC, `[[TN,FP],[FN,TP]]` 혼동행렬을 보고합니다. 유형별 Precision/Recall/F1과 양성/음성·대화/그룹 지원 수, Micro F1, 정의 가능한 유형의 Macro F1과 정의된 유형 개수도 보고합니다. 기본 주 결과는 모든 실험에서 **risk 0.5·8유형 각 0.5**로 고정합니다. sigmoid는 한 번 적용하고 유형 판정은 이진 판정으로 차단하지 않습니다.

양성 없는 유형은 recall/F1/AUC를 N/A와 사유로 표시합니다. 현재 TEST 후보의 앱 설치·비밀유지는 해당됩니다. 정의 가능한 6개 유형의 macro를 8종 전체 macro로 부르지 않습니다. PR35의 undefined 처리와 다르게 임의의 0을 채워 순위를 만들지 않습니다.

현재 매우 적은 positive·독립 그룹 수를 고려해 이 프로토콜의 주 비교는 탐색적 이진 F1 및 부수 지표입니다. 8종 우월성이나 실통화 일반화의 확증 실험으로 포장하지 않습니다. TEST 위협 양성은 1개, 개인정보는 2개라 작은 변화가 큰 지표 차이를 만들 수 있습니다.

별도 임계값 최적화는 이번 계획의 주 비교에 넣지 않습니다. 추후 검증된 validation에서 threshold 정책을 연구한다면 모든 arm에 같은 사전 등록 탐색 범위·선택 기준을 적용하고 그 결과를 별도 보조 표로 기록해야 합니다. 양성 수가 부족한 유형은 개별 threshold 탐색을 금지하고 0.5를 유지합니다. 어떤 경우에도 TEST로 임계값·loss·seed를 고르지 않습니다.

## 반복·불확실성·오류 분석

seed별 원 지표와 3개 seed의 평균·표준편차를 나란히 제공합니다. 표준편차는 학습 난수 변동이며 데이터 불확실성 CI와 구별합니다. 같은 TEST 독립 그룹을 A/B/C에서 함께 재표집하는 paired cluster bootstrap 2,000회, seed `20261107`, percentile 95% CI와 ΔF1을 보조 보고할 계획입니다. 발화가 아니라 독립 연결 그룹을 표집 단위로 사용합니다. 양성/음성이 빠진 반복은 해당 지표 N/A로 두고 유효 반복 수와 이유를 보고합니다. 10개 TEST 대화·소수 양성 그룹에서는 CI도 불안정하다는 한계를 유지합니다.

최종 평가 후 FP/FN은 대화·출처·위험 유형·정상 hard negative·현재 과거 5발화의 가시성으로 분석합니다. 정상 상담의 공식 소속 소개, 정당한 본인 확인, 정상 결제, 동의 기반 지원을 오탐과 구분합니다. 평가용 답을 보고 다시 학습해 같은 TEST에서 개선을 주장하지 않습니다.

## 구현·출력 경계

실행 설정은 [A.json](../../experiments/koelectra_v2/configs/A.json), [B.json](../../experiments/koelectra_v2/configs/B.json), [C.json](../../experiments/koelectra_v2/configs/C.json)입니다. 입력·split·손실 가중치 파일 SHA를 확인하며, 실험·시드·run별 `artifacts/v2_comparison_runs/{experiment}/seed_{seed}/{run_id}/model.pt`를 예약하도록 준비했습니다. 기존 run 디렉터리가 있으면 거부하고 기존 v1 경로를 허용하지 않습니다.

현재 runner는 preflight만 지원하며 실제 학습 CLI가 아닙니다. 기존 PR35의 in-sample 평가 CLI는 학습 sample count·data_version·과거 canonical 체크포인트를 가정하므로 공통 holdout 평가에 그대로 쓰면 안 됩니다. 향후 evaluator는 선택된 공통 holdout ID와 checkpoint의 split/데이터/프로토콜 해시를 대조해 inference·공통 metrics 함수를 호출하고 새로운 출력 경로에만 기록해야 합니다. 이번에 평가를 실행하거나 그 부분이 검증 완료됐다고 표시하지 않았습니다.
