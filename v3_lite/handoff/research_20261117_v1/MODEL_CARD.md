# KoELECTRA v3 Lite research — trained, not adopted over v2

v2 B_ratio/seed42/epoch3의 encoder와 두 head를 이어 학습했다. 새 AdamW, LR5e-6, batch8, weight_decay0.01, pos_weight10, seed42, FP32, CPU2threads/gradient checkpointing을 사용했다. 실제 1epoch/106steps/848샘플을 처리했다. 평균 loss는 0.6600795072(risk0.2104133383/type0.4496661665), 학습 본체는 1238.187초였다. 전체201텐서가 바뀌었다(encoder197/risk2/type2).

부모 SHA는 `0d14fadcc9dbd1a3ea3872074970d47f79148f76766d77188eb808b94ed9d2ee`다. 기반 `monologg/koelectra-base-v3-discriminator`, revision `68b30cd259f34a4b5aa8786392612ba2a2617fcc`와 tokenizer/입력/8종 순서를 유지했다.

부모는 기존 미검수 llm_synthetic656발화의 학습 이력을 갖는다. 신규192발화도 AI 잠정 라벨이며 사람이 검수하지 않았다. purpose=internal_experiment, source_kind=llm_synthetic, human_reviewed=false, approved_for_production=false, deployment_allowed=false다. 내부 연구 허용과 사람 검수·운영 승인은 별개다.

새 합성 VALIDATION32대화/256발화에서 위험F1은 .7563→.8276, 정보탐색F1은 .0000→.4167, 정상 대화FP는 6/12→3/12였다. 개인정보F1 .4375→.4211/AP .5754→.4790, 대출F1 .5714→.4348은 악화됐다. 안전 제약은 통과했지만 전체 개선 목표와 epoch2 조건은 실패했다. **v2 대체 모델로 채택하지 않으며**, 실제 학습한 epoch1을 연구 결과로 보존한다.

새 VALIDATION은 같은 작성 세션의 미검수 합성 선택 집합이며 최종 TEST가 아니다. 실제 통화/ASR/운영 일반화는 미확정이다. 기존 v2 TEST를 재개방하지 않았고, 결과를 본 뒤 데이터/threshold/seed/LR를 다시 선택하지 않았다. 실서비스 배포를 권고하지 않는다.

파일·SHA·크기·tensor 계약은 CHECKPOINTS.json, 로딩 방법은 SERVER_HANDOFF.md에 있다. 추론 파일은201모델 텐서를 보존하고 optimizer buffers를 제외했다. 독립 CPU 검증은 통과했지만 실제 backend/HTTP 연동은 수행하지 않았다.
