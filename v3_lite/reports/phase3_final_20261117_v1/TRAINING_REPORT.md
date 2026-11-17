# 실제 KoELECTRA v3 Lite 연구 학습 완료

공개 encoder를 새로 학습한 것이 아니라 v2 B_ratio/seed42/epoch3의 encoder와 두 head를 복원했다. 초기201상태 텐서의 해시를 동결했고, 새 AdamW(lr5e-6,weight_decay0.01)로 시작했다. 부모 optimizer state는 이어받지 않았다.

| epoch | step | samples | total loss | risk loss | type loss | 초 | 변경 tensor |
|---|---|---|---|---|---|---|---|
| 1 | 106 | 848 | 0.660080 | 0.210413 | 0.449666 | 1238.19 | 201 |


실제 처리: 전체 KoELECTRA forward/loss/backward/optimizer.step, 기존656+신규192=848 TRAIN 샘플. batch8,seed42,FP32,CPU2threads,gradient checkpointing,기존 loss/pos_weight10,threshold0.5를 유지했다. epoch별 encoder/risk/type 그룹의 실제 변경 수와 유형별 loss는 TRAINING_HISTORY.json에 있다.

시작 실패1회는 baseline의 NumPy int64 JSON 저장 오류이며 **업데이트0**이었다. 데이터·LR·선택 gate를 바꾸지 않고 저장 타입과 회귀 검사를 고친 뒤 새run_id v2로 재실행했다. 점수가 불리해서 재실험한 것이 아니다. 원래 실패 디렉터리도 로컬에 보존했다.

실제 결과를 보고 데이터·threshold를 다시 쓰지 않았다. epoch2 여부는 동결된 조건만 따랐다. 종료 상태는 NO_IMPROVEMENT_CANDIDATE_ADOPTED이다. 학습 체크포인트 파일은 CHECKPOINT_MANIFEST.json에 기록했다. CPU 독립 검증 및 추론 전용 파일 결과는 최종 인계 보고서를 함께 본다.
