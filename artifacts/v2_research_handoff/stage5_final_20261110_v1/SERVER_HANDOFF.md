# 서버 담당자용 최종 연구 인계

이 패키지는 기존 준비본을 덮어쓰지 않은 새 버전이다. 실제 서버 전송/배포를 수행한 것은 아니다. 운영 배포 승인과 사람 라벨 검수 완료 상태는 false다.

모델 파일·SHA:
- seed 42: `models/B_ratio/seed_42.pt` SHA-256 `0d14fadcc9dbd1a3ea3872074970d47f79148f76766d77188eb808b94ed9d2ee`
- seed 43: `models/B_ratio/seed_43.pt` SHA-256 `612a27419bff738b7661552b152ee37eb8b463e14dcbaaed8200b44796703fae`
- seed 44: `models/B_ratio/seed_44.pt` SHA-256 `92970156e78ad1aa4b10e17e0386124b1fdc0f67c2b2ab194fc6bde27b7bc409`

신뢰할 bundle_manifest.json SHA-256: `fd452646aee020276888aea89f80667ac76b43234d634d1b600a744f9e99adc9`.
기존 준비본 manifest SHA-256: `812612cf3bc0987123e6c6ffb7f896ecd93b596b468f21a92adf51cb32445112`.
동결 평가 계획 SHA: `2735f1879489da64149811277de40da3669e5341eec0d37a1f47afb59dab845c`.

패키지의 models/tokenizer/vendor/stage5_runtime.py/bundle_manifest.json을 함께 복사하고 SHA를 검증한다. 로컬 모델 파일은 원본과 같은 하드 링크이므로 수정하지 말고, 인계 대상 서버로는 새 파일 복사본을 전달한다. 실제 검증된 의존성은 requirements-tested.txt에 있다. 전체 플랫폼 휠 잠금이나 실제 서버 호환성 검증을 대신하지 않는다.

```powershell
python stage5_runtime.py --bundle . --seed 42 --manifest-sha fd452646aee020276888aea89f80667ac76b43234d634d1b600a744f9e99adc9
```

표준입력 JSON 예: `{"history_texts":[],"current_text":"공식 안내문을 제가 직접 확인하겠습니다."}`.

Python 연결은 ResearchPredictor(bundle_path, seed=42, expected_manifest_sha=위해시)와 serve_request(predictor, request_json)를 사용한다. 정상 결과는 ok=true/result 객체, 실패는 ok=false/result=null이다. 오류를 정상으로 변환하지 않는다. INVALID_REQUEST/INVALID_JSON=400, INPUT_TOO_LONG=422, NOT_READY=503, TOKENIZER_CONTRACT/MODEL_INFERENCE_ERROR=500이다.

입력은 [CLS] history [SEP] current [SEP], 과거 최대 5발화, 줄바꿈 연결, token_type_ids 0/1, 오른쪽 padding, 최대512토큰이다. 넘치면 오래된 history 전체 발화를 제거하고 현재만으로 넘치면 INPUT_TOO_LONG으로 실패한다. ASR/마스킹/전사 교정은 제공하지 않는다. 두 헤드는 독립이다.

기본 seed42의 실제 TEST 이진 F1 0.9400, AP 0.9694, 정상 대화 오탐 3/8다. 세 seed 평균과 구분한다. TEST를 본 뒤 기본 seed를 바꾸지 않았다. MODEL_CARD.md/DATA_CARD.md/TEST_COMPARISON.md의 한계를 함께 인계한다.
