# 1인 검수 완료 TRAIN 후보

`pilot_single_review_train_candidate.jsonl`은 임정윤의 승인 136행에 근거한 16대화 후보입니다. 정본의 대화·발화 구조와 순서·텍스트·라벨·생성/수정 이력을 보존하고 `review_preparation`에 1인 검수 출처를 추가했습니다.

**2인 최종 승인 데이터가 아닙니다.** 김해린과 최종 합의의 미승인 상태는 유지하며 기존 `approval_*/pilot_approved.jsonl`을 변경하지 않았습니다. 실제 학습·기존 v1 학습 데이터 병합은 수행하지 않았습니다.

`v1_adapter_label_candidates.jsonl`과 `v1_adapter_text_candidates.jsonl`은 Git에서 복원한 `risk_speech_ai.training_data.build_training_samples`의 별도 입력입니다. 내부 `label_status=reviewed`는 1인 타깃 검수 상태이며 최종 승인을 의미하지 않습니다. 모든 행에 `approval_stage=single_review_train_candidate`, `final_approved=false`를 명시했습니다. 실제 검수 시각은 추정하지 않았습니다.

`v1_adapter_sample_candidates.jsonl`은 해당 기존 샘플 생성기를 실제 실행한 출력입니다. 생성 모델과 수정 이력 등 전체 메타데이터는 대화 단위 후보와 `conversation_provenance.jsonl`에 보존합니다. 텍스트 변환은 원본과 동일한 identity mapping이며 새 발화나 교정 텍스트를 생성하지 않았습니다.

변환기는 `dataset/scripts/prepare_v2_training_candidate.py`이며 `--allow-single-review-candidate` 명시 옵션이 필요합니다. 최신 실제 DataLoader 실행 결과·중복 검사 범위·남은 문제는 `reports/v2_pilot/ml_runtime/README.md`를 확인합니다. `training_readiness/`의 보고서는 그 이전 샘플 연결 단계의 기록입니다.
