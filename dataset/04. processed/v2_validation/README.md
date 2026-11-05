# 독립 합성 VALIDATION 후보

`validation_24_generated.jsonl`은 24대화·192발화이며 모두 `split=validation`, `review_status=generated`입니다. 사람 승인 및 TRAIN 반영은 없습니다.

`scenario_registry.json`의 24개 가족과 대화 전개를 이후 TRAIN 생성에 재사용하지 마세요. 실제 v1 입력과의 중복 검사는 미확보로 미검증입니다.

`evaluation_label_candidates.jsonl`의 라벨 상태는 `unreviewed`입니다. 기존 학습 샘플 생성기는 192개를 모두 제외합니다. 평가 어댑터가 기존 Dataset/DataLoader의 실행 호환성만 검사하며 이 파일들을 TRAIN에 합치거나 승인 상태를 올리면 안 됩니다.

전체 결과와 재실행 방법은 [검증 보고서](../../../reports/v2_validation/README.md), 검수 자료는 `dataset/review/v2_validation/human_review.csv`에 있습니다. 이 합성 후보는 실제 통화의 최종 성능 입증 자료가 아닙니다.
