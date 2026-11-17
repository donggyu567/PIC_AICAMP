# 체크포인트 보존·무결성 확인

복구 확인일:2026-11-18. 학습은 다시 실행하지 않았다. 기존 파일을 읽어 실제 크기와 SHA-256을 재확인했다.

| 구분 | 실제 프로젝트 상대 경로 | bytes | SHA-256 |
|---|---|---:|---|
| training | `v3_lite/runs/research_synthetic_seed42_20261117_v2/epoch_001.pt` | 1,348,303,402 | `607005ca8ce0e5a1352b4624eb49eab44f66015af58487396fe5b815cc9bfda9` |
| inference | `v3_lite/handoff/research_20261117_v1/models/v3_seed42_inference.pt` | 449,438,496 | `35dae5286fb4f39f23821989da6e3afcee5d9827197969e6ec88d09e47d083c2` |
| parent | `.worktrees/koelectra-v2-pilot-readiness/artifacts/v2_research_handoff/stage5_final_20261110_v1/models/B_ratio/seed_42.pt` | 1,348,303,914 | `0d14fadcc9dbd1a3ea3872074970d47f79148f76766d77188eb808b94ed9d2ee` |

학습용은 model_state_dict/optimizer_state_dict/training_config/label_order/base_model/metadata와 v3 계보를 보존한다. 실제 epoch1/106updates/848샘플이다. 추론용은201모델 텐서를 그대로 보존하고 optimizer buffers를 제외했다. v1 envelope 호환 키 optimizer_state_dict는 빈 dict다. schema와 tensor shape·dtype는 `../../handoff/research_20261117_v1/CHECKPOINTS.json`에 있다.

독립 CPU 검증에서 학습/추론201텐서가 모두 일치하고 부모 대비201개 변경(encoder197/risk2/type2)이 확인됐다. 이는 새 랜덤 모델을 부모 이어 학습으로 표시한 결과가 아니다. 현재 파일 SHA와 runtime/tokenizer 지문이 그 검증 당시와 같아 결과를 재사용한다. `v3_lite/checkpoints/` 권장 폴더 대신 실제 학습기는 기존 설계대로 runs/<새ID>를 사용했다. 같은 모델의 불필요한 복사본은 만들지 않았다.
