# KoELECTRA v2 1차 결과

2026-11-09 KST. 동기화 기준 HEAD는 `01323989dad907a38e5fcca9fce0537adc070e32`, 브랜치는 `feat/koelectra-v2-pilot-readiness`다. 최종 결과는 이 디렉터리를 추가한 Git 커밋으로 식별한다. 원격 fetch 및 `pull --ff-only` 완료, 기존 v1 작업 폴더의 미커밋 변경은 보존했다.

|결과물|파일|
|---|---|
|기술 정합성·Git·자산 점검|[technical_alignment.md](technical_alignment.md)|
|TRAIN80/독립VALIDATION32/봉인TEST40 설계와 유형별 부족분|[data_design.md](data_design.md)|
|기존 A/B/C를 보존한 실험 개정안|[experiment_protocol.md](experiment_protocol.md)|
|재사용 코드·2차 구현과12단계 의존성|[dependencies.md](dependencies.md)|
|별도 schema의 실행 전 설계 계약|[protocol_20261109_v1.json](../../experiments/koelectra_v2/protocol_20261109_v1.json)|
|실제 수량·검수 CSV·가중치 파일 해시|[inventory.json](inventory.json)|
|설정·참조·승인 차단 검증|[protocol_validation.json](protocol_validation.json)|
|현재 PC의 CPU DataLoader 검증|[cpu_preflight.json](cpu_preflight.json)|
|최종 파일별 독립 프로세스 회귀 결과|[tests.json](tests.json)|
|기존1026파일·가중치3개의 보존|[preservation_result.json](preservation_result.json)|

**테스트146개 통과**: 기존 v2 89개, PR35 데이터/토큰/지표48개, 신규 contract9개. 단일 프로세스 discover의 스냅샷 import 충돌과 추가 PR35 suite의 최초 PYTHONPATH 누락은 각각 `single_process_initial.log`, `tests_initial_import_path.json`에 보존했다. 최종 suite는 모두 exit0이다. 원본 코드를 바꾸지 않고 suite별 별도 프로세스 및 PR35 경로 지정으로 재실행했다.

CPU에서는 TRAIN208개/52배치, 보조VALIDATION192개/48배치 모두 확인했다. TEST는 읽거나 평가하지 않았다. 모델 학습·새 대화 본문 생성·검수 승인·가중치 수정·PR·merge는 수행하지 않았다. 기존 A/B/C를 포함한 모든 기존 tracked 파일1026개가 동일하며 v1 두 사본과 공개 encoder 가중치도 동일하다.

과거 v2 보고서와 달리 현재 기본 작업 폴더에는 알려진 v1 SHA와 일치하는 체크포인트 두 사본이 있다. 이번에는 파일·해시만 검증했고 모델 로드·metadata·추론을 확인한 것이 아니다. 이 바이너리들은 커밋 대상이 아니다.

생성 후보 기준 TRAIN은24→80까지56개 부족하고, 독립VALIDATION32개와 봉인TEST40개는 전부 새로 확보해야 한다. 기존 LLM VALIDATION24개는 독립32개에 포함하지 않는다. 기존 TRAIN 최종 승인0이므로 검수·사용승인 기준 부족은80개 전체다. 원본 추진안 파일과 유형별 원래 추가 양성 목표는 미확보여서 그 수치 대비 부족분은 확인 불가로 남겼다. 별도 양성 목표 제안은 원문 수치로 표시하지 않았다.

**2차 코드 구현 착수 가능, 실제 학습은 차단**이다. v1 적격권한 manifest, approved TRAIN80 manifest, 독립VALIDATION32 manifest, 봉인TEST40 메타데이터 영수증은 아직 없고 `protocol_validation.json`에 명시돼 있다. 인간 작성·권한·2인 검수·최종 사용승인과 성능 합격 기준의 실제 담당자 결정이 필요하다.

현재 PC 검증 Python은 기본 작업 폴더 `.venv-ai/env/Scripts/python.exe`이며 Python3.11.16, torch2.6.0+cpu, transformers4.57.6이다. 환경·캐시를 Git에 포함하지 않는다. 작업 트리 루트에서 이 Python으로 다음을 실행할 수 있다.

```text
python -B -X utf8 experiments/koelectra_v2/validate_stage1.py
python -B -X utf8 experiments/koelectra_v2/check_stage1_suites.py
python -B -X utf8 experiments/koelectra_v2/audit_stage1.py cpu
python -B -X utf8 experiments/koelectra_v2/audit_stage1.py verify
```

CPU 검증은 이 PC의 기본 작업 폴더 캐시를 참조한다. 다른 PC에서는 고정 revision tokenizer 캐시의 위치를 명시해 adapter를 조정해야 한다. 캐시가 없으면 다운로드하거나 가짜 토크나이저로 대체하지 않고 실패한다. 보존 검증은 이번 시작 시 기록한 `preservation_before.json`과의 비교이며, 미래 정상 변경을 승인하는 도구가 아니다.
