# KoELECTRA v3 Lite — 실제 개발 완료 범위

**모델 학습 및 체크포인트 생성: 완료**

**연구용 합성 VALIDATION 평가: 완료**

**종합 개선 목표 달성 및 v2 대체 채택: 미달**

**사람 검수·실환경 검증·운영 배포: 미완료**

학습일2026-11-17, 중단 복구·제출 정리일2026-11-18. 재학습하지 않고 검증된 산출물을 재사용했다. 기존 v1/v2·TEST·PR#35/#37은 보존한다. PR은 미병합 v2에 의존하는 stacked 구조로 별도 제출한다.

| 항목 | 결과 |
|---|---|
| 신규 합성 TRAIN/VALIDATION |24대화·192발화 /32대화·256발화 |
| 최종 TRAIN |기존80/656+신규24/192=104대화/848발화 |
| 실제 학습 |seed42,1epoch,106 optimizer updates |
| 평균 loss |total0.6600795072/risk0.2104133383/type0.4496661665 |
| 학습 본체 시간 |1238.187초(약20분38초) |
| 저장된 변경 텐서 |201(encoder197/risk2/type2) |
| 동일 신규 VALIDATION 위험F1 |0.7563→0.8276 |
| 정보탐색 TP/F1 |0→5 /0.0000→0.4167 |
| 정상 대화 FP |6/12→3/12 |
| 개인정보 F1/AP |0.4375→0.4211 /0.5754→0.4790 |
| 대출 유형 F1 |0.5714→0.4348 |
| epoch2/대체 채택 |사전 조건 실패로 실행/채택하지 않음 |

개인정보 FP32→27은 감소했으나 TP14→12/FN4→6으로 미탐이 늘었다. 정보탐색도18양성 중13개를 여전히 놓쳤다. 양성 강조·문맥 분리·결정 경계 변화 가능성은 있지만 관측 한 번으로 원인을 확정하지 않는다. 데이터·seed·LR·threshold를 결과에 맞춰 다시 선택하지 않았다.

기본 설정은 LR5e-6/batch8/AdamW 새 상태/weight_decay0.01/pos_weight10/FP32/기존 구조·tokenizer·입력·8종순서/9threshold0.5다. 부모 가중치를 strict 복원하고 원본 파일과 학습용 storage를 분리했다. 연구용 허용은 정식2인 검수 게이트와 분리했다. 신규와 부모의 미검수 합성 계보를 유지한다.

내부 원본 테스트31 PASS(기존27포함), v2 core unit48 PASS, 독립 모델/CLI CPU 검증 PASS. 복구 당시 소스 해시가 기존 PASS receipt와 동결 학습 코드에 일치함을 확인했다. 공개 checkout 검사 결과는 FINAL_EXECUTION_SUMMARY.md에 별도 기록한다. Android/서버 전체 suite나 기존 TEST 평가를 재실행한 결과가 아니다.

근거: TRAINING_REPORT.md, VALIDATION_COMPARISON.md/json, CHECKPOINT_REPORT.md, INFERENCE_SMOKE.md, TRAINING_POLICY.md, NORMAL_HARD_NEGATIVES.md. 인계: `../../handoff/research_20261117_v1/`의 MODEL_CARD/DATA_CARD/SERVER_HANDOFF/DRIVE_DELIVERY 및 manifest. 새 독립 TEST와 실제 통화/STT/운영 검증은 없다.
