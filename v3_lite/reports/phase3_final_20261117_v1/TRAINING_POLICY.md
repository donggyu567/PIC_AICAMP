# 연구용 정책과 정식 승인 경로 분리

이번 사용자의 명시적 지시는 자체 합성 데이터 생성과 내부 연구용 학습을 허용한다. 기존 v2 stage4도 llm_synthetic/provisional/internal_experiment 경로에서 학습했으며 정식 운영 승인으로 위장하지 않았다. 프로젝트의 raw 실수집 디렉터리나 제3자 자료를 사용하지 않았다.

새 research_synthetic_v3 경로는 purpose=internal_experiment,source_kind=llm_synthetic,human_reviewed=false,human_review_complete=false,approved_for_production=false,deployment_allowed=false를 요구한다. formal data.load_manifest/load_training_inputs는 독립2인 검수·권한 증빙 요건을 계속 유지한다. 연구 manifest를 정식 corpus로 로딩하면 실패한다. 사람 검수 기록이나 승인 시각을 생성하지 않았다.

기존 미검수 합성 TRAIN80/656과 부모 가중치 계보도 유지한다. v2 VALIDATION32/256은 회귀 진단에만 쓰고 TRAIN에 합치지 않았다. v2 TEST 원문·암호문·개별 예측·정답·해제/단일실행 원본은 접근하지 않는다.

실제 신규 합성 발화는 Codex 세션이 개별 시나리오 문장을 작성한 것이며 코드가 문장을 반복 치환해 채운 것이 아니다. 정확한 backend model ID는 주장하지 않는다. 별도 AI 재독과 자동 검사는 사람 검수나 의미 독립성 증명이 아니다. 원문/생성 초안/사용자 승인 원본은 Git에 제외하고 통계·해시·정책만 공개한다.

최초 코드의 data/README.md와 phase2 문서는 검수된 자료를 요구하던 이전 단계의 계약이다. 그 정식 경로를 완화하지 않고 이번 명시 허용에 맞는 별도 연구 경로를 추가했다. 사람 검수, 새 독립 TEST, 실제 서버 통합, 운영 배포 승인은 여전히 별도 미완료다.
