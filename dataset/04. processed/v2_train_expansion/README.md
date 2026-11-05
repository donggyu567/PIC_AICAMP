# TRAIN 0017~0024 신규 및 24대화 통합 후보

`train_0017_0024_generated.jsonl`은 신규 8대화·72발화이며 모두 `split=train`, `review_status=generated`입니다.

`train_24_mixed_review_candidate.jsonl`은 기존 후보의 바이트 16대화와 신규 8대화를 순서대로 합친 24대화·208발화 파일입니다. 기존 `review_preparation`은 그대로 유지하며 신규에는 사람 승인이나 검수 완료 상태를 부여하지 않았습니다. 최종 승인·학습 허용 데이터가 아닙니다.

`cpu_dry_run_*`는 실행 호환성 검사용입니다. 신규 라벨은 `unreviewed`이며 일반 안전 샘플 생성기는 신규 72개를 제외합니다. 전체 208개 DataLoader 검증은 별도 실행 검사용 어댑터에서만 수행했고, 이 파일들을 실제 학습에 사용하지 않았습니다.

생성 이력·입력 및 생성 해시는 `generation_and_scenarios.json`, 상세 결과·재실행·사람 검수 항목은 [검증 보고서](../../../reports/v2_train_expansion/README.md)에 있습니다. 기존 TRAIN과 VALIDATION은 수정하지 않았으며 VALIDATION 자료를 이 파일에 혼합하지 않았습니다.
