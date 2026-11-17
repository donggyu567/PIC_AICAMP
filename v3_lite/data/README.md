# v3 Lite 데이터 제출 계약

현재 실제 신규 corpus와 사용권한·사람 검수 기록은 없다. `tests/fixtures.py`는 자동 테스트용이며 확보 수량에 포함하지 않는다. 자동 검증으로 사람 승인 기록을 생성하지 않는다.

1차 규모를 유지한다: TRAIN24대화/192발화(정보탐색6·개인정보6·정상12), 새 VALIDATION32대화/256발화(목표유형각6·정상12·나머지위험8). 목표유형은 각 분할에서 각각18양성/6가족 이상이어야 한다. 새 분할은 미리 고정하고 독립 작성·2인 검수한다.

## 버전 디렉터리

`data/<version>/manifest.json`, `train_additions.jsonl`, `validation_new.jsonl`, `train_reviews.jsonl`, `validation_reviews.jsonl`, `legacy_focus_reviews.jsonl`, `split_review.json`, 출처별 권한JSON을 준비한다. 모든 참조는 같은 버전 안의 상대경로와 실제 SHA-256 쌍이어야 한다. 파일 밖/TEST/봉인 경로는 거절한다. 실제 파일이 없는 빈 corpus/가짜 해시 manifest를 만들지 않는다.

manifest 필드:

- `schema="v3-lite-data/1"`, `purpose="internal_experiment"`, `artifact_kind="research_corpus"`, 정식 `label_order`8개
- `production_training_authorized=false`, `deployment_approved=false`, `no_v2_test_derivation=true`
- `splits.train`, `splits.validation`: 정해진 JSONL 파일의 `{path,sha256}`
- `reviews.train`, `reviews.validation`, `reviews.legacy_focus`: 각 검수JSONL의 `{path,sha256}`
- `split_review`: 분할검수JSON의 `{path,sha256}`

대화 필드: `conversation_id`(V3-시작), `family_id`, `split`, `source`, `category`(financial/official/identity/app/quotation), `review_status="reviewed"`, `provenance`, `rights`, `utterances`.

provenance에는 method, author_or_generator, created_at, origin_id, semantic_family_id가 필요하다. 실제 수집·작성/생성 사실을 적는다. v2 TEST를 재개방해 대조하지 않으며 v2 문장 치환·TEST 유래를 새 자료로 등록하지 않는다. TRAIN/VALIDATION 간 가족·의미가족·출처계보는 분리한다. 가족 단위 독립성은 ID만 바꾸어 증명되지 않는다.

rights에는 `status="documented"`, `permitted_uses`와 권한JSON 참조가 필요하다. 권한JSON은 `record_type="data_use_authorization"`, `status="confirmed"`, `source_ids`, `permitted_uses`, `authorized_by`, timezone 포함 `authorized_at`, `basis`를 갖는다. 실제 통화는 적법한 동의·학습/평가 목적·재배포/보관 범위를 확인하고 비식별화한다. 프로젝트 시뮬레이션도 생성·작성 출처와 사용 근거를 남긴다.

발화는 순차 `utterance_id`1~8, speaker_A/B, text, bool `is_phishing`, canonical 순서의 `labels`, `masking_reviewed=true`를 갖는다. 정상은 labels=[]이고 위험은1개 이상이다. 허용 개인정보 토큰은 기존9개이며 원시 전화번호/주민번호/계좌/이메일 등은 마스킹한다. 자동 패턴 검사는 누락을 모두 찾지 못하므로 사람 검수도 필수다. history를 입력에서 받지 않고 기존 v2 `causal_samples`로 이전 최대5발화만 만든다.

## 독립 2인 검수와 합의

각 발화 검수JSONL은 conversation_id/utterance_id, `content_sha256`(`data.utterance_binding` 결과), `record_type="human_review"`, `status="resolved"`, reviewers2개를 갖는다. 각 reviewer는 서로 다른 실제 reviewer_id, human=true, independent=true, timezone 포함 reviewed_at, is_phishing/labels 판정을 기록한다. 이름·시각·판정을 자동 생성하지 않는다.

불일치가 있으면 resolution에 실제 adjudicator_id/reason/resolved_at/최종 is_phishing·labels를 남긴다. 마스킹·텍스트·정답이 바뀌면 기존 검수 해시가 무효가 되므로 재검수한다. 이 코드가 실제 사람의 독립성을 인증할 수는 없다. 담당자는 검수 출처와 기록의 진위를 확인해야 한다.

기존 TRAIN의 목표양성45발화+정상210발화도 검수해야 한다. `legacy_focus_reviews.jsonl`은 원본 발화·라벨에 바인딩한다. 정정이 필요하면 현재 loader는 학습을 차단한다. 원본을 고치지 말고 별도 파생 뷰/검수 이력을 설계해 새 버전으로 반영해야 한다. 검수되지 않은 나머지 기존 v2 라벨 및 부모 가중치 이력은 잠정 상태로 유지한다.

split_review는 `record_type="human_split_review"`, status=resolved, reviewed_at, human_reviewer_ids2개, semantic_independence_reviewed=true, no_test_derivation=true, bindings를 갖는다. bindings는 train/validation/legacy_train/legacy_validation의 실제 데이터SHA다. ID·가족 및 대화 전체 정규화 유사도0.8 이상 후보를 차단한다. 이 자동 검사는 의미 독립성/TEST 비중복을 증명하지 않는다. 새 독립 TEST는 별도 보관자가 개발 자료와 분리해 수집해야 한다.

## 실행

데이터 준비 후 소스가 일치하는 회귀 receipt를 먼저 생성하고 아래처럼 실행한다. 데이터/권한/사람검수/분할/부모SHA/저장경로/자원 중 하나라도 실패하면 업데이트하지 않는다.

```powershell
.venv-ai/env/Scripts/python.exe -B -X utf8 -m v3_lite.src.train --manifest v3_lite/data/<version>/manifest.json --run-id <새-ID> --regression-receipt v3_lite/reports/<검증버전>/regression.json
```

이 진입점은 연구 전용이며 정식/운영 학습 승인으로 사용하지 않는다. 사람이 검수한 신규 데이터가 있어도 모델 전체가 사람 승인된 것으로 바뀌지 않는다.
