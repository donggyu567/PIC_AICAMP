# v1 자산 복구 및 v2 학습 파이프라인 점검

**v1 학습 입력 2개를 과거 기록의 SHA-256과 정확히 일치하게 복구했습니다. 학습된 v1 체크포인트는 NOT_FOUND입니다.** v2 TRAIN 208발화와 VALIDATION 192발화는 분리된 실제 CPU DataLoader 검증을 통과했지만, 일반 학습 경로의 승인 조건은 충족하지 못했습니다.

|대상|상태|실제 확인 결과|
|---|---|---|
|v1 `labels.jsonl`·`tuned.jsonl`|**READY — EXACT HASH RECOVERY**|원자료 Git 커밋과 기록된 준비 로직으로 복구; 두 SHA-256 모두 과거 기록과 동일, 68대화·1,460발화|
|v1 `koelectra_risk_v1.pt`·`risk_speech_v1.pt`|**NOT_FOUND**|로컬 프로젝트·관련 폴더·Git/LFS·PR35 tree·관련 ZIP·연결 Drive 검색에서 실제 가중치 미발견|
|v1 체크포인트 CPU 로딩|**BLOCKED**|파일 미확보로 실행하지 않음; 무작위 모델을 v1 대신 사용하지 않음|
|v1 독립 TRAIN/VALIDATION 분할 manifest|**NOT_FOUND**|PR35는 TRAIN IN-SAMPLE, 독립 validation/test 없음으로 명시. 미래 split 계획 코드를 과거 분할로 간주하지 않음|
|v1 모델 설정·평가 소스·실행 기록|**READY — DOCUMENTARY/SOURCE ONLY**|고정 PR35 코드·기록·기반 모델 config 확보. 실제 체크포인트 내부 metadata는 미검증|
|v1 학습 당시 정확한 코드 snapshot|**NOT_FOUND / NOT_RECORDED**|당시 미커밋 수정사항의 snapshot이 기록되지 않음; PR35 소스를 당시 학습 실행과 완전히 동일하다고 주장하지 않음|
|v2 TRAIN·VALIDATION CPU 사전 검증|**READY — PREFLIGHT ONLY**|208+192=400발화, 52+48=100배치, 문맥·토큰·패딩·타깃 전체 통과|
|v2 일반 학습 승인|**BLOCKED**|2인 최종 합의 및 별도 학습 사용 결정 미충족; 엄격한 게이트에서 학습 적격 0/208|
|문자열·ID·가족 분리 검사|**READY — LEXICAL SCREEN COMPLETE**|TRAIN↔VALIDATION ID·가족·시나리오 충돌 및 완전·정규화·0.80 이상 문장 후보 0|
|의미적 시나리오 독립성·라벨 품질|**BLOCKED — HUMAN REVIEW REQUIRED**|문자열 검사로 증명 불가. 검토할 132발화·시나리오 9쌍 제공|
|실제 학습·성능 비교 시작|**BLOCKED**|승인·모델 초기화 자산·안전한 학습 진입점 및 출력 경로·사람 검토가 남음|

## v1 원자료와 실제 학습 입력 복구

현재 로컬 Git에는 원자료 커밋 `8faa6a7eebfe95c7ac7fe6c6077a49ebf31f958f` 객체가 없었지만, GitHub에서 해당 커밋과 완전한 tree를 확인했습니다. 현재 로컬 파일을 원본으로 가정하지 않고 Git blob ID와 크기를 대조했습니다. 일치하는 로컬 원본 및 GitHub에서 받은 원래 버전을 별도 `artifacts/v1_recovered_8faa6a7eebfe/source_snapshot/`에 저장했습니다. 기존 dataset은 덮어쓰지 않았습니다.

고정 PR35의 원래 준비 함수를 사용하되 원자료 읽기만 메모리에서 복구 snapshot으로 연결했습니다. 역사적 학습 사용 상태 필드를 재현했으며, 새 사람 승인이나 v2 학습 권한을 부여하지 않았습니다. 처음 LF 직렬화에서는 해시가 불일치해 실제 입력으로 저장하지 않았고, 원래 Windows `Path.write_text(newline=None)`의 CRLF 직렬화를 재현한 뒤 두 해시가 모두 일치했습니다. 최초 불일치 기록도 보존했습니다. 합성 대화를 생성한 작업이 아닙니다.

|복구 파일|크기|실제 SHA-256 = PR35 기록|
|---|---:|---|
|[labels.jsonl](../../artifacts/v1_recovered_8faa6a7eebfe/prepared/labels.jsonl)|800,984 bytes|`c205049e1aa2125ad40cc6cea1465b2c2793cc7fedf02b7eab8e1d9f20e9c9e5`|
|[tuned.jsonl](../../artifacts/v1_recovered_8faa6a7eebfe/prepared/tuned.jsonl)|499,774 bytes|`50ea88cc3ee9c3df1477082ab5daf82ef77f83329374b50f312874592462e6f2`|

실제 입력 1,460개는 기존 샘플 생성기에서 모두 처리됐습니다. 기존 제외 사유도 동일하게 사용 권한 미확인 24, 마스킹 단계 미확인 53, 위험 유형 미확정 67, 미지원 토큰 30개로 총 174개입니다. 복구 파일의 역사적 `approved_for_training`은 원래 파일의 바이트를 복구한 결과이며 현재 v2나 다른 데이터의 승인을 뜻하지 않습니다.

## 가중치와 과거 설정 탐색

[PR35](https://github.com/donggyu567/PIC_AICAMP/pull/35)는 현재 open·미병합이고 head는 `9bab7e383928426e2d866de90acae013fe1f7d86`입니다. 새로 확인한 [인계 문서](https://github.com/donggyu567/PIC_AICAMP/blob/9bab7e383928426e2d866de90acae013fe1f7d86/risk_speech_ai/CHECKPOINT_HANDOFF.md)는 가중치가 Git/LFS에 없고 외부 공유도 미실행이라고 명시합니다. 현재 PR 댓글과 해당 커밋의 Actions workflow run 목록도 비어 있습니다. PR35 재귀 tree와 실제 원자료 커밋 tree에서 prepared 입력 및 `.pt`가 추적되지 않는 점을 확인했습니다.

로컬 프로젝트, Downloads, Documents, OneDrive 문서, `.codex/worktrees`, 관련 Desktop 폴더, 기본 Hugging Face 캐시를 지정 탐색했습니다. Downloads의 관련 ZIP 12개는 멤버 이름까지 확인했으며 가중치·원래 prepared 입력은 없었습니다. Documents의 접근 오류 3개는 [탐색 기록](local_asset_search.json)에 그대로 남겼고, 접근 불가 영역을 검사 완료로 간주하지 않았습니다. 최초 경로 계산 오류 기록과 수정 후 실제 탐색 기록을 구별했습니다. 모든 디스크·다른 사람 컴퓨터를 조사했다고 주장하지 않습니다.

연결된 Google Drive에서 두 체크포인트 파일명을 검색했습니다. 실제 바이너리는 없었고 `risk_speech_v1.pt` 검색의 유일한 결과는 학습 작업 지시 Google Doc이었습니다. 이 문서를 가중치로 분류하지 않았습니다. Git LFS의 Android STT·PII NER 모델은 v1 위험 분류 가중치와 구분했습니다.

가중치 수령 시 필요한 실제 파일은 두 이름 중 하나입니다.

|필요 자산|기록된 기대값 또는 조치|
|---|---|
|`koelectra_risk_v1.pt` 또는 `risk_speech_v1.pt`|1,348,308,730 bytes, SHA-256 `1131f9dcc665f79073d98ecd6845573109a89e44dbf2917d299a8fea057020a7`|
|파일 전달 경로|원래 학습 PC 보유자 또는 허용된 인계 위치에서 원본 파일 수령; 이번 작업에서 타인에게 메시지를 보내지는 않음|
|파일 확보 후 검사|SHA·크기 → `torch.load(weights_only=True, map_location='cpu')` → schema v1·8유형 순서·encoder config·tokenizer 지문·입력 계약 → 실제 모델 state 로딩|
|연결된 설정|기반 모델 `monologg/koelectra-base-v3-discriminator`, 모델/토크나이저 revision `68b30cd259f34a4b5aa8786392612ba2a2617fcc`, 이진 head 1·유형 head 8|
|문서상 실제 학습 설정|CPU, 1 epoch, batch 8, AdamW, LR 2e-5, weight decay 0.01, seed 42, 183 steps|

위 설정은 보존된 실행 기록·기반 모델 설정에서 확인한 값입니다. 미확보 체크포인트 metadata를 실제로 읽은 결과는 아닙니다. 독립 v1 validation/test가 없다고 명시돼 있으므로 새로 분할해 과거 독립 평가 결과라고 부르지 않습니다.

## 72발화 제외와 파이프라인 장애물

상세 분석은 [pipeline_blockers.md](pipeline_blockers.md)에 있습니다. 핵심은 신규 `unreviewed`를 `reviewed`로 바꾸는 것이 해결책이 아니라는 점입니다.

|경로|현재 동작|
|---|---|
|PR35 기존 안전 샘플 생성기|1차 208개 결합 → 신규 미검수 72개 제외 → 기존 136개 선택. 2차 안전 문맥 구성에서는 제외 본문이 없어 `missing_tuned_text=72`로 집계|
|엄격한 v2 일반 학습 게이트|TRAIN만 허용, 현재 원문과 일치하는 전체 검수표·두 사람 승인·실제 검수 시각·최종 합의·미해결 의견 없음·데이터에 결부된 학습 사용 결정을 요구. 현재 전체 208개 차단|
|v2 `preflight`|명시한 단일 split만 허용. 미승인 합성 라벨로 기존 `TrainingSample`과 실제 Dataset/DataLoader 실행 형식만 확인. `training_allowed=false`|

PR35 내부 생성기는 `split`, `final_approved`, `training_eligible`를 권한 조건으로 검사하지 않습니다. 현재 데이터에서도 `training_eligible=false`인 기존 136개를 선택합니다. 테스트용 독립 fixture로 잘못된 validation/`reviewed` 메타데이터를 내부 생성기가 받아들이는 것도 확인했습니다. 실제 VALIDATION 라벨의 승인 상태를 바꾸거나 학습시키지는 않았습니다.

따라서 새 [v2_pipeline_gate.py](../../dataset/scripts/v2_pipeline_gate.py)의 게이트를 거치지 않고 PR35 원시 CLI를 실제 v2 학습에 사용하면 안 됩니다. 이번에는 그 원시 CLI나 고정 소스를 수정하지 않았고, 실제 학습 기능도 호출하지 않았습니다. 학습을 허용하는 최종 실행 명령과 출력 체크포인트 경로는 후속 구현·검증이 필요합니다.

## 실제 실행과 데이터 누출 검사

|항목|TRAIN|VALIDATION|
|---|---:|---:|
|대화 / 발화|24 / 208|24 / 192|
|실제 CPU 배치, batch size 4|52|48|
|첫 배치 입력 shape|[4,83]|[4,94]|
|이진 / 8유형 타깃|[4,1] / [4,8]|[4,1] / [4,8]|
|dtype / 장치|입력 int64·타깃 float32 / CPU|입력 int64·타깃 float32 / CPU|
|같은 대화의 이전 최대 문맥|5발화, 전체 208개 확인|5발화, 전체 192개 확인|
|입력 토큰 길이 / 제거 문맥|20~163 / 0|18~144 / 0|

두 split은 따로 변환·로딩했습니다. 총 400개에서 실제 `[CLS] history [SEP] current [SEP]`, segment 0/1, 토큰·마스크·패딩·현재 타깃·문맥을 확인했습니다. 모델 순전파·backward·optimizer·체크포인트 저장은 0입니다. 새 검증 1,633개와 관련 테스트 93개가 모두 통과했습니다.

|문자열 비교|비교 쌍 수|완전·정규화 일치|유사도 0.80 이상 후보|
|---|---:|---:|---:|
|v2 TRAIN ↔ v2 VALIDATION|39,936|0|0|
|v2 TRAIN ↔ 실제 v1 입력|303,680|0|1|
|v2 VALIDATION ↔ 실제 v1 입력|280,320|0|0|

유사 후보는 `SYN2-TRAIN-0011-2`의 **저는 교체 신청을 한 적이 없는데요.**와 실제 v1 `P0005-5`의 **저는 카드 신청한 적이 없는데요.**이며 유사도는 **0.814815**입니다. 일반적인 피해자 반응 표현의 유사성이므로 대화 전체 재사용 여부를 별도로 검토하고 원문은 보존했습니다.

NFKC·casefold·공백/Unicode 구두점 제거 뒤 `SequenceMatcher(autojunk=False)`로 비교했습니다. 0.80 미만임이 확실한 상한만 가지치기했으며, 가지치기한 전체 쌍의 최고 유사도를 측정했다고 주장하지 않습니다. 실제 v1에는 시나리오 가족 정보가 없어 **v1 대비 의미적 가족 독립성은 사람 확인 전**입니다. 0.80 이상 문장 후보가 없는 VALIDATION도 의미적 독립성이나 실제 통화의 최종 성능이 증명된 것은 아닙니다.

## 승인·라벨 검토

|검수 상태|TRAIN 208|VALIDATION 192|
|---|---|---|
|김해린|208 미승인|192 미승인|
|임정윤|136 승인·72 미승인|192 미승인|
|최종 합의|208 미승인|192 미승인|
|현재 2인 최종 검수 충족|0|0|

기존 136개의 임정윤 승인 표시는 보존했지만 검수 시각 열은 공란입니다. 검수 시각을 추정하거나 자동 입력하지 않았습니다. 두 사람 검수와 실제 시각, 최종 합의, 별도 학습 사용 결정을 확보해야 일반 학습 경로를 열 수 있습니다. 현재 v1의 과거 학습 사용 정책을 v2 승인으로 가져오지 않았습니다.

[human_review_cases.csv](human_review_cases.csv)는 **132발화**의 ID·원문·현재 라벨·근거·이전 최대 5발화·검토 사유·변경 제안을 포함합니다. 신규 멀티라벨 3개, 0020 전체, 신규 정상 4대화와 VALIDATION 정상 8대화의 모든 96발화, v1 유사 후보, 초기 소속 소개의 실시간 식별 가능성을 다룹니다. 모든 상태는 `needs_human_review`이며 사람 승인 결과를 생성하지 않았습니다.

[semantic_scenario_pairs.csv](semantic_scenario_pairs.csv)는 **9쌍의 양쪽 전체 원문**을 제공합니다. 특히 0020↔기존 TRAIN 0009 및 VALIDATION 0001, TRAIN의 앱 요구↔VALIDATION 앱 요구, 허위 대출·학교 계정 수집↔다른 허위 대출 가족을 비교해야 합니다. 정상 본인 확인 사례도 서로 다른 split에서 같은 전개를 단순 반복했는지 확인해야 합니다.

초기 소속 소개의 `institution_impersonation`은 전체 시나리오의 사칭 설정을 근거로 붙어 있지만 모델에는 미래 발화·시나리오 요약이 들어가지 않습니다. 정상 소속 소개와 현재 접두 문맥만으로 구별 가능한지를 별도 검토 항목으로 남겼습니다. 가이드가 허용하는 전체 문맥 정답을 자동 오류로 단정하거나 라벨을 반전하지 않았습니다.

## 주요 결과물

|파일|용도|
|---|---|
|[asset_inventory.json](asset_inventory.json)|자산별 READY/NOT_FOUND·실제 경로·크기·SHA·모델 설정 근거|
|[v1_input_recovery.json](v1_input_recovery.json)|원자료 blob별 검증 및 실제 입력 해시 일치 증거|
|[local_asset_search.json](local_asset_search.json), [git_search_evidence.json](git_search_evidence.json)|탐색 범위·접근 오류·Git/LFS 결과|
|[pipeline_result.json](pipeline_result.json)|승인 게이트·분리 CPU 실행·1,633개 검사|
|[pipeline_blockers.md](pipeline_blockers.md)|실제 장애물과 필요한 후속 조치|
|[independence_result.json](independence_result.json)|실제 v1 및 두 split의 문자열 비교 결과·후보 원문|
|[human_review_cases.csv](human_review_cases.csv), [human_review_cases.jsonl](human_review_cases.jsonl)|132발화 검토 목록; 원래 검수표와 분리|
|[semantic_scenario_pairs.csv](semantic_scenario_pairs.csv)|9쌍 시나리오 전체 원문 비교|
|[v1_conversation_review_index.csv](v1_conversation_review_index.csv)|실제 v1 68대화의 의미적 중복 검토용 원문 색인|
|[related_tests.json](related_tests.json)|새 게이트 16·기존 확장 16·VALIDATION 13·고정 PR35 비학습 48 = 93개 테스트|
|[protected_baseline.json](protected_baseline.json)|작업 전 기존 961파일 SHA-256|
|[audit_v2_pipeline.py](../../dataset/scripts/audit_v2_pipeline.py), [v2_pipeline_gate.py](../../dataset/scripts/v2_pipeline_gate.py)|실행 검증과 명시적 승인·분할 게이트|
|[recover_v1_inputs_audit.py](../../dataset/scripts/recover_v1_inputs_audit.py)|과거 해시가 일치할 때만 입력을 복구하는 재현 코드|

재실행은 다음과 같습니다. 기존 생성 스크립트나 기존 보고서 생성기를 실행하지 않으며, 아래 점검 코드는 해당 점검 폴더의 보고서만 갱신합니다.

```powershell
& '.venv-v2/Scripts/python.exe' -B -X utf8 dataset/scripts/recover_v1_inputs_audit.py
& '.venv-v2/Scripts/python.exe' -B -X utf8 dataset/scripts/audit_v2_pipeline.py
& '.venv-v2/Scripts/python.exe' -B -X utf8 dataset/scripts/write_v2_pipeline_review_queue.py
& '.venv-v2/Scripts/python.exe' -B -X utf8 -m unittest discover -s tests -p test_v2_pipeline_gate.py -v
```

기존 정본·검수 CSV·기존 보고서·고정 소스·기존 런타임 자산 961개는 해시가 그대로입니다. 이번 결과는 이전 보고서의 v1 입력 `미확보` 상태를 복구·해시 검증 완료로 갱신하는 새 증거이며 이전 보고서는 보존했습니다. 추가 합성 데이터 생성·학습·임계값 최적화·v1 체크포인트 변경·Commit·Push·PR 생성은 수행하지 않았습니다.
