# 실험 프로토콜 개정안

버전은 `koelectra-expansion-20261109-v1`, machine-readable 설정은 `experiments/koelectra_v2/protocol_20261109_v1.json`이다. 기존 `configs/A.json`, `B.json`, `C.json`, split/weight manifest와 runner는 원본 그대로 보존했다. 새 JSON은 독립 schema의 **설계 계약**이며 기존 runtime에 전달해 실행하는 설정이 아니다. `validate_stage1.py`는 해시·경로·역할·금지된 실행 플래그·라벨 순서와 미확보 입력을 검증할 뿐 trainer를 실행하지 않는다.

|신규 arm|기존 대응|자료|구분할 효과|
|---|---|---|---|
|A0|A|적격 기존 v1 TRAIN|무가중 BCE,1 epoch, threshold0.5. 과거 가중치 복원이 아닌 재학습 기준|
|A_epoch|A 확장|A0와 동일|1/2/3 epoch만 비교|
|B_ratio|B 개정|A와 동일|각 epoch에서 비율 pos_weight 상한10; A_epoch 동일 epoch와 비교|
|B_threshold|B 별도 평가 정책|B_ratio와 동일 체크포인트|독립 VALIDATION에서 선택한 epoch와 threshold 효과를 고정0.5 결과와 별도 보고|
|C_approved|C 개정|B와 같은 적격 v1 + 최종 승인 신규 TRAIN|B에서 고른 epoch·weights·threshold·seed 고정, 승인된 합성 추가 효과 비교|
|B_step_matched|기존 보조 계획 대응|B의 적격 v1만 반복|C와 같은 optimizer step 수로 계산량 차이 진단|

기존 B/C의 제곱근·상한5는 legacy ablation으로만 보존하며 비율·상한10과 동일하다고 부르지 않는다. 기존 48/10/10은 새 arm의 split이 아니다. 현재 새 TRAIN 권한 manifest, approved80, 독립32, 봉인40 영수증은 실제 파일이 없으며 설정에 `available=false`로 표시했다. 경로가 생겨도 승인으로 간주하지 않고 다음 프로토콜 버전에서 해시·결정 근거를 동결해야 한다.

## 공통 조건과 가중치

공개 KoELECTRA 고정 revision, 공통 encoder·1/8 출력, 5발화 문맥·512토큰·현재 발화 라벨, 동일 입력 전처리·seed42/43/44를 유지한다. AdamW, batch8, LR2e-5, weight decay.01, float32, risk/type loss 계수1/1을 사용한다. 새 encoder·통화 head·증류는 추가하지 않는다. tokenizer revision/어휘 해시, 라이브러리 lock, 학습 장치·thread·determinism도 실제 실행 전에 기록한다. 이번 PC는 Python3.11.16·torch2.6.0+cpu·transformers4.57.6으로, 과거 v2 보고서 Python3.12.14와 달라 비트 단위 재현을 주장하지 않는다.

기본 유형 가중치는 `min(10,max(1,N_negative,k/N_positive,k))`다. 승인된 **기존 v1 TRAIN**의 현재 발화 라벨에서만 계산하고 VALIDATION/TEST는 절대 포함하지 않는다. 양성0이면 weight1 및 unsupported를 기록해 탐지 학습 가능하다고 주장하지 않는다. 이진 BCE는 무가중이다. 새 적격 manifest가 없으므로 이번에는 실행용 weight vector를 만들어 확정하지 않는다. 참고용 현재 후보의 양성 통계는 점검 inventory에만 있다.

C는 B의 가중치 벡터를 재사용한다. 추가 합성으로 다시 가중치를 계산하면 데이터 추가와 손실 변경이 섞이므로 별도 실험 버전으로만 허용한다. B와 C는 같은 초기 공개 encoder와 seed별 새 head 초기값에서 각각 시작한다. C가 B의 학습 완료 가중치를 이어받는 fine-tuning 실험으로 바뀌지 않도록 한다. 같은 epoch의 C는 업데이트 수가 늘어나므로 품질만의 인과 효과로 단정하지 않고 B_step_matched의 결과도 제시한다.

## 선택 규칙 사전 등록

1. A_epoch와 B_ratio는1/2/3 epoch 체크포인트를 비교하되 같은 epoch의 손실 차이 표를 유지한다. B의 배포 후보 epoch는 독립 VALIDATION의 **고정0.5 이진 F1, 세 seed 평균** 최대값으로 선택한다. 동률이면 작은 epoch다. seed 자체를 점수로 선택하지 않는다. 과거 1epoch A0는 항상 별도 기준으로 남긴다.
2. 선택된 B epoch에서 이진/각 유형 threshold를 독립 VALIDATION만 사용해 `.10,.15,...,.90` grid로 탐색한다. 각 output의 seed평균 F1 최대, 동률이면0.5에 가까운 값, 다시 동률이면 높은 threshold를 선택한다. 모든 seed에 같은 벡터를 적용한다. 유형별 양성/음성 각각10발화·양성3대화 미만이면 탐색하지 않고0.5를 유지한다. 이진도 같은 최소 지원 조건을 적용한다.
3. 이렇게 정한 B의 epoch·threshold 벡터를 C에도 그대로 적용해 B→C 비교에서 재선택이 끼지 않도록 한다. 향후 C 전용 재튜닝은 별도 버전/보조 실험이다. 고정0.5와 선택 threshold 결과는 별도 표다.
4. 별도 TRAIN 사용 승인·검수·새 독립 validation gold와 protocol/data/split/threshold 해시 동결이 없으면 위 선택을 실행하지 않는다. TEST는 모델·epoch·weight·threshold·seed 선택에 사용하지 않는다.

같은32대화에서 epoch와 threshold를 모두 고르는 소규모 선택 편향을 한계로 명시하고 후보군을 확대하지 않는다. 성능 합격 목표(최소 recall/허용 오탐률)는 원본 추진안 미확보로 미확정이며 팀 책임자가 운영 목적과 함께 실제 학습 전에 결정해야 한다. 이 설계의 선택 규칙을 성능 합격 기준으로 바꾸어 설명하지 않는다.

## 평가·출력

최종 평가는 이진 precision/recall/F1/ROC-AUC와 `[[TN,FP],[FN,TP]]`, 유형별 precision/recall/F1·support, micro F1, 정의된 유형 macro와 정의된 유형 수를 보고한다. 양성 없는 유형은 N/A·사유, 일부만 정의되면 완전8종 macro라고 부르지 않는다. 유형 판정은 sigmoid1회 후 개별 threshold이며 이진 판정으로 차단하지 않는다. 정상 hard negative의 FP/전체 정상 수, 정상 대화 중 하나라도 FP인 비율, 유형·출처·가족별 FP/FN과 지원 수를 함께 보고한다.

seed별 원값·평균·표준편차와, 최종 독립 가족을 단위로 하는 paired bootstrap2000회(seed20261107) ΔF1/95% CI를 계획한다. 계산 불가능 반복은 제외 사유·유효 반복 수를 명시한다. 인간 작성 시뮬레이션 성능과 실제 통화 일반화는 구분한다. 최종 TEST 오류 분석 후 같은 TEST에 재튜닝해 개선을 주장하지 않는다.

향후 출력은 `artifacts/v2_comparison_runs/expansion_20261109_v1/{arm}/seed_{seed}/{run_id}/model.pt`로 분리한다. 실제 writer에서 resolve containment·새 디렉터리 독점 생성·기존 run 거부·v1 경로 거부를 강제해야 한다. protocol/data/split/approval/weight/threshold/epoch/seed/step metadata를 검증한 후에만 inference를 허용한다. 이번에는 해당 trainer/writer/evaluator가 구현됐다고 표시하지 않으며 checkpoint를 생성하지 않는다.
