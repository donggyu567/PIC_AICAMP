# v1_retrained_baseline 재학습 계획

이 문서의 모델은 새 **v1_retrained_baseline**입니다. 과거 v1 가중치 복원본이 아닙니다. 이번에는 실제 학습·optimizer·backward·성능 측정을 수행하지 않았습니다.

## 확인한 과거 설정

근거는 고정 PR35 `9bab7e383928426e2d866de90acae013fe1f7d86`의 `model.py`, `training.py`, `tokenization.py`, `inference.py`, `metrics.py`, `evaluate_cli.py` 및 `artifacts/risk_speech_ai/reports/reproducibility.json`입니다.

|항목|확인한 값|증거 수준|
|---|---|---|
|기반 모델|`monologg/koelectra-base-v3-discriminator`|소스·실행 기록|
|모델/토크나이저 요청 revision|`68b30cd259f34a4b5aa8786392612ba2a2617fcc`|실행 기록; 토크나이저 resolved revision은 null|
|텍스트|검증된 마스킹 원문을 `tuned_text` 호환 필드에 그대로 사용, LLM 보정 없음|해시 일치 입력·소스·기록|
|문맥|같은 대화의 이전 적격 발화 최대 5개, 줄바꿈 구분|공통 입력 코드|
|입력 형식|`[CLS] history [SEP] current [SEP]`, 최대 512, 오른쪽 동적 패딩|공통 입력 코드|
|길이 초과|가장 오래된 history를 발화 단위로 제거, 현재 발화 단독 초과는 오류|공통 입력 코드|
|구조|KoELECTRA encoder의 첫 토큰 hidden state → 독립 Linear head [B,1], [B,8]|모델 소스|
|학습 범위|encoder와 두 head 모두 학습|학습 소스|
|실제 epoch / batch|1 / 8; CLI 기본 3 epoch와 구별|실행 기록|
|Optimizer / LR / weight decay|AdamW / 2e-5 / 0.01|기록·소스|
|손실|이진·유형 각각 mean BCEWithLogitsLoss, 가중치 1.0+1.0, pos_weight 없음|소스·기록|
|Seed / 장치|42 / CPU|기록|
|원래 학습량|68대화·1,460발화, 183 optimizer steps|기록; 가중치 내부 값은 미확인|
|체크포인트 선택|마지막 epoch|고정 소스|
|추론|raw logits에 sigmoid 한 번, 이진 및 유형별 기본 threshold 0.5|추론·평가 소스|
|유형 판정|이진 결과로 차단하지 않고 8개 확률에 독립 threshold 적용|추론 코드|
|과거 평가|동일 학습 1,460발화의 TRAIN IN-SAMPLE, holdout 없음|평가 소스·기록|

임계값 판정은 `>=`이며 평가 전 확률을 반올림하지 않습니다. 이진 혼동행렬은 `[[TN,FP],[FN,TP]]`입니다. PR35 metrics는 양성이 없는 유형의 recall/F1/AUC를 null과 사유로 기록하고, macro F1은 정의 가능한 유형만 평균하며 `defined_f1_labels`를 함께 제공합니다. 이번 비교도 이 의미를 보존하되 8개 중 일부가 정의 불가능하면 **8종 전체 macro 성능은 추정 불가**로 표시합니다.

## 확인할 수 없는 부분

- 실제 v1 체크포인트 및 그 내부 metadata·optimizer state.
- 당시 미커밋 코드의 정확한 snapshot. 현재 고정 PR 소스는 재현 준비의 근거이며 비트 단위 동일 실행을 보장하지 않습니다.
- optimizer betas/eps를 별도로 지정했는지에 관한 과거 기록, 정확한 CPU thread 설정·완전한 실행 시간·배치별 loss.
- 토크나이저 resolved revision 기록. 대신 요청 revision·어휘 지문·실제 동작을 고정합니다.
- 과거 환경은 Python 3.11.16, 현재는 3.12.14입니다. torch 2.6.0+cpu와 transformers 4.57.6은 같아도 정확히 같은 수치 결과는 보장하지 않습니다.

## 새 기준 모델 A

공정 비교용 A는 복구한 v1 자료의 **공통 TRAIN 후보에 해당하는 48대화·943발화만** 사용하도록 설정했습니다. 공통 validation/test 후보 20대화·517발화는 학습에서 제외합니다. 따라서 68대화 전체를 학습했던 과거 실행의 데이터 양까지 동일하게 재현하는 실험은 아닙니다. 이 차이는 독립 평가를 마련하기 위해 필요하며 결과 이름은 `A_v1_retrained_baseline`으로 고정합니다.

선택된 943발화 기준 epoch 1·batch 8의 계획 업데이트 수는 118입니다. 과거 183 steps를 이 실험의 실제 steps로 복사하지 않습니다. 실제 학습은 아직 없으므로 학습 loss·F1·소요 시간을 보고하지 않습니다.

원래 1,460발화 전부를 1 epoch 학습하는 **별도 recipe replay**가 필요하면 별도 run으로 계획할 수 있습니다. 그 모델은 같은 68대화에서 만든 내부 holdout을 이미 보게 되므로, 공정 비교용 A와 혼합하거나 해당 내부 TEST의 독립 성능을 보고하면 안 됩니다. 이번에는 이 full-data 모델도 학습하지 않았습니다.

## 공개 기반 모델 확보 결과

원래 v1 체크포인트에 의존하지 않도록 공개 encoder의 고정 revision을 프로젝트의 별도 `artifacts/v2_experiment_assets/` 캐시에 내려받았습니다. config·tokenizer_config·vocab은 Git blob과, 가중치는 원격 LFS SHA-256과 대조했습니다.

- `pytorch_model.bin`: **451,741,507 bytes**, SHA-256 `f3f249cc07826bc2964a2c0dbbd0d239df4fe55efc03ba33e1bd1584cf56c566`.
- 실제 encoder와 새 이진/8유형 head 구성을 오프라인으로 로딩했습니다. 파라미터 112,337,673개, hidden size 768, head weight shape [1,768]·[8,768].
- task head는 seed 42로 새로 초기화한 가중치입니다. 원래 v1의 task head가 아니며 학습된 v1 분류기 성능을 입증하지 않습니다.
- 이 로딩 검사는 optimizer·모델 forward·backward 없이 수행했습니다. 손실 함수 자동 테스트는 별도 작은 텐서 fixture만 사용했습니다.

근거: [public_base_assets.json](public_base_assets.json), [preflight_A.json](preflight_A.json). 공개 모델 출처는 [고정 Hugging Face revision](https://huggingface.co/monologg/koelectra-base-v3-discriminator/tree/68b30cd259f34a4b5aa8786392612ba2a2617fcc)입니다. 네트워크 기본 sandbox의 WinError 10013 후 허용된 다운로드 실행으로 확보했고, 패키지는 새로 설치하지 않았습니다.

실제 학습 전에는 분할·중복 예외·평가 정답 품질을 사람이 확인한 뒤 새 입력/설정 해시를 동결하고 별도 학습 사용 결정을 받아야 합니다. 현재 실행 도구는 의도적으로 `preflight`만 지원합니다.
