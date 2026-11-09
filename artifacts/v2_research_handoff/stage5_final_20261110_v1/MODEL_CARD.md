# 최종 연구용 모델 카드

중요한 TEST 한계: information_probing은 seed42·43·44 모두 F1=0이다. 개인정보 요구는 평균 F1=0.2945이며, 기본 seed42의 유형 오탐은 74개다. 기본 seed42의 정상 대화 이진 오탐은 3/8=37.5%다. 8종 모두를 안정적으로 탐지한다고 표시해서는 안 된다.

B_ratio epoch3, seed42·43·44 전체를 TEST 이전 후보로 고정했고 변경하지 않았다. 서버 기본 seed42는 기존 기본값/등록 seed 최솟값 규칙이며 TEST 성능으로 고르지 않았다. 9개 threshold는 모두 0.5, 버전은 exploratory-validation-grid-v1이다.

최종 합성 TEST B_ratio 이진 F1 평균 0.9231 ± 0.0363, AP 0.9487, 정상 대화 오탐률 평균 0.2500. 개인정보 F1 평균 0.2945, AP 평균 0.7222. 이 값은 세 seed 지표 평균이며 단일 서버 seed42의 성능이나 확률 ensemble 성능이 아니다. 개별 seed와 v1/A_epoch 비교 및 가족 불확실성은 TEST_COMPARISON.md에 있다.

- seed 42: `models/B_ratio/seed_42.pt` SHA-256 `0d14fadcc9dbd1a3ea3872074970d47f79148f76766d77188eb808b94ed9d2ee`
- seed 43: `models/B_ratio/seed_43.pt` SHA-256 `612a27419bff738b7661552b152ee37eb8b463e14dcbaaed8200b44796703fae`
- seed 44: `models/B_ratio/seed_44.pt` SHA-256 `92970156e78ad1aa4b10e17e0386124b1fdc0f67c2b2ab194fc6bde27b7bc409`

공개 베이스와 tokenizer revision은 68b30cd259f34a4b5aa8786392612ba2a2617fcc이며 monologg/koelectra-base-v3-discriminator를 사용했다. 유형 순서는 ['institution_impersonation', 'money_transfer', 'personal_information', 'app_installation', 'secrecy', 'threat_pressure', 'loan_fraud', 'information_probing']다. 위험 여부와 유형은 독립 헤드, 현재 발화 판정이며 누적 위험 값이 아니다.

TEST 평가는 명시 승인 후 1회 수행했지만 데이터는 llm_synthetic/provisional, 사람 라벨 검수 미완료다. 실제 운영 배포 승인은 없다. 합성/공통 작성자 스타일, 작은 정상·유형 가족 지원, 의미적 독립성 미확인, 실제 통화·ASR 분포 차이와 개인정보 취약성을 고려해야 한다. 추가 실제 통화 검증과 별도 배포 승인 없이 운영 가능성이 입증됐다고 표시하지 않는다. 재학습이나 TEST 기반 재선택은 없었다.
