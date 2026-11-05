# KoELECTRA v2 Commit/Push 전 공개 범위 점검

사용자의 실제 Commit/Push 지시에 따라 `d8c9fb2` 이후 생성한 v2 데이터·검수 준비·검증·v1 복구·실험 설계 결과를 기존 `feat/koelectra-v2-pilot-readiness` 브랜치에 선별합니다. 모델 학습 및 추가 A/B 학습 구현은 하지 않습니다.

## 포함

- VALIDATION 24대화·192발화와 미승인 2인 검수표.
- 신규 TRAIN 8대화·72발화, 기존 16대화를 보존한 통합 24대화·208발화 후보 및 미승인 검수표.
- CPU DataLoader·승인/분할 게이트·회귀 테스트·품질/누출 점검 보고서.
- 실제 v1 prepared 입력 68대화·1,460발화의 **마스킹된** `labels.jsonl`, `tuned.jsonl`; 과거 SHA-256과 일치함을 확인.
- A/B/C 설계·조건부 분할 후보·공개 모델 자산의 metadata와 preflight 결과. 모델 가중치는 포함하지 않음.
- 공개 전 검사 코드·검사 결과·테스트 기록. 실제 파일 목록과 SHA는 `publication_audit.json`에 기록하며 자기 자신은 hash 목록에서 제외합니다.

## 로컬에 보존하고 제외

|대상|사유|
|---|---|
|`artifacts/v1_recovered_8faa6a7eebfe/source_snapshot/` 전체 70파일|일부 staging 본문에 미마스킹 전화번호, masked 소스의 `raw_text`에 이메일 등이 남음. 실제 여부를 추정하지 않고 원자료 사본 전체를 보수적으로 제외|
|`reports/v2_pipeline_audit/recovered_source_payloads.json`|위 미마스킹 원자료를 담은 API 응답 payload|
|`reports/v2_pipeline_audit/audit_*.json`, `drive_checkpoint_search*.json`|원자료 diff가 들어갈 수 있는 원시 GitHub 캡처·개인 Drive 검색 metadata 등 디버그 원본. 공개용 요약·hash·결과 보고서는 포함|
|`.venv-v2/`, 모델/cache·checkpoint·Python 캐시|실행 환경과 대용량 가중치 제외. 공개 기반 encoder는 별도 로컬 캐시이며 기록만 포함|
|`phishing_candidate_research_jeongyun_202609w4.md`|이전부터 제외한 관계없는 개인 문서. 사용자 지시에 따라 계속 제외|
|`reports/v2_publish/initial_scan.json`, `*.nul`|검사 초안과 선택 스테이징용 임시 pathspec 파일|

원문을 마스킹해 원래 파일·해시를 바꾸는 방식은 사용하지 않았습니다. 제외 파일은 삭제하지 않았으며 원자료/덤프/개인 노트의 실수 재추가를 막는 ignore 규칙을 추가했습니다. 새 복제본에는 raw snapshot·connector payload가 없으므로 과거 전체 복구의 로컬 증거를 재실행하려면 해당 원자료를 통제된 방법으로 별도 확보해야 합니다. 마스킹된 prepared 입력은 포함돼 실험 설정·테스트에서 그대로 사용할 수 있습니다.

## 검사와 바이트 보존

초기 정규식의 전화/RRN 후보 일부는 40/64자리 Git·SHA 값의 숫자 부분이었습니다. 실제 대화 필드와 기술 hash를 구분해 다시 검사했고, 공개 대상의 본문·CSV·JSON·코드에서 credential/식별자 패턴을 확인했습니다. 신규 합성 대화의 가상 기관·마스킹 토큰, 미승인 상태도 별도로 확인했습니다. 패턴 검사가 모든 개인정보 부재를 증명한다고 주장하지 않습니다. 의심 원자료는 제외해 보호합니다.

`core.autocrlf=true` 환경에서 복구된 prepared 입력(CRLF)과 검수 CSV의 바이트가 Git에서 변환되면 기존 SHA와 달라집니다. 기존 정책을 확장한 `.gitattributes`로 이번 데이터·코드·보고서의 바이트를 보존하고, 스테이징 blob과 로컬 SHA를 대조합니다. 기존 TRAIN 정본·검수 기록·고정 v1 코드·복구 입력의 본문은 수정하지 않았습니다.

신규 TRAIN 72발화 및 VALIDATION 192발화의 두 검수자·최종 합의 결과는 전부 미승인입니다. 기존 136발화의 1인 검수 상태와 복구한 v1 입력의 역사적 `approved_for_training`은 보존하며, 이를 v2 최종 승인으로 승격하지 않았습니다.

자동 테스트는 `test_results.json`, 최종 공개 검사 및 선택 파일 목록은 `publication_audit.json`에 있습니다. 모든 root 테스트 모듈을 각각 독립 프로세스로 실행하고, pinned PR35의 비학습 data/tokenization/dataset/metrics/split 테스트를 추가 실행합니다. 실제 학습이나 optimizer 테스트는 실행하지 않습니다.

과거 보고서와 baseline은 당시 로컬 실행의 기록입니다. 이번에 승인된 Git commit으로 HEAD가 달라진 뒤에도 이전 baseline의 HEAD를 현재 상태로 간주하거나 과거 보고서를 무작정 재생성하면 안 됩니다.
