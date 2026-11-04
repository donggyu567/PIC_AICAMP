# v2 파일럿 정본 복원·검증 결과

자동 구조 검증 통과. 사람 검수 및 학습 사용 승인은 미완료입니다.

- 정본: `dataset/04. processed/v2_pilot/pilot_canonical.jsonl` (UTF-8, 1대화/1행)
- TXT 3개를 SHA-256으로 고정하고, 4대화 + 신규 12대화 + 0003-10 명시 수정 + 최신 7대화 전체 교체 순서로 복원했습니다.
- 0003-10은 `네, 그럼 이만 끊겠습니다.`로 반영했습니다. 그 외 임의 문장·라벨 수정은 없습니다.
- 원본 generation_model, revision_history 및 generated 상태를 보존했습니다. 원본 모델의 실제 실행 환경은 검증하지 않았습니다.
- 원본 TXT와 기존 데이터는 수정하지 않았습니다. 모델 학습·Git push는 수행하지 않았습니다.

| 항목 | JSON 본문 재계산 | 마지막 TXT 집계표 |
|---|---:|---:|
| 대화 | 16 | 16 |
| 발화 | 136 | 136 |
| 피싱 발화 | 34 | 32 |
| 정상 발화 | 102 | 104 |
| 양성 라벨 합계 | 37 | 35 |

멀티라벨 때문에 양성 라벨 합계와 피싱 발화 수는 다릅니다.

| 라벨 | JSON 본문 재계산 |
|---|---:|
| institution_impersonation | 10 |
| money_transfer | 3 |
| personal_information | 4 |
| app_installation | 7 |
| secrecy | 5 |
| threat_pressure | 3 |
| loan_fraud | 3 |
| information_probing | 2 |

## 사람 검수 사항

- 최신 설명표는 0006-7의 피싱 라벨을 제거했다고 하지만 JSON에는 비밀 유지 요구와 true/[secrecy]가 남아 있습니다.
- 최신 집계표의 app_installation=6·secrecy=4와 달리 본문은 각각 7·5입니다. 집계표에 맞추려고 본문을 변경하지 않았습니다.
- SYN2-TRAIN-0006: 수정 이력에 없는 실제 변경 발화=[4, 6]; 이력에는 있지만 본문 차이가 없는 발화=[]. 상세 전후값은 restoration_manifest.json에 있습니다.
- SYN2-TRAIN-0007: 수정 이력에 없는 실제 변경 발화=[5]; 이력에는 있지만 본문 차이가 없는 발화=[]. 상세 전후값은 restoration_manifest.json에 있습니다.
- SYN2-TRAIN-0015: 수정 이력에 없는 실제 변경 발화=[7]; 이력에는 있지만 본문 차이가 없는 발화=[]. 상세 전후값은 restoration_manifest.json에 있습니다.
- 원본이 지정한 경계 사례(0005-7 앱 실행, 0006 사칭 전제, 0007 조직 사칭, 0009-5 대출 미끼, 0010-5 결제, 0011 탐색, 0015 가상 신청 절차)를 검수해야 합니다.

## 중복 검사

- 로컬 v1 raw/staging/masked 797개 파일, 발화 버전 1281개와 비교했습니다.
- 파일럿 내 완전 동일 발화 그룹: 1; 정규화 동일 그룹: 1.
- 파일럿 내 대화 유사도 0.90 이상: 0; 로컬 v1 동일 발화 후보: 0; 로컬 v1 유사 대화 후보: 0.
- 중복 후보는 삭제하지 않았습니다. 로컬에 없는 v1 자료 및 의미적 중복은 검증 범위 밖입니다. 정규화·유사도 방식과 후보 위치는 duplicate_report.json에 있습니다.

## 재실행

저장소 루트에서 실행합니다. 이 환경에는 Python이 PATH에 없어서 검증에 사용한 런타임 경로를 명시했습니다. 다른 환경에서는 Python 3.10+ 경로로 바꾸면 됩니다.

```powershell
& 'C:\Users\임정윤\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -B dataset/scripts/restore_pilot.py --check-only
& 'C:\Users\임정윤\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -B -m unittest discover -s tests -p test_restore_pilot.py -v
```

`--check-only`는 정본을 덮어쓰지 않고 TXT와 비교하며 보고서만 갱신합니다. 최초 복원은 옵션 없이 실행합니다. `--original-dir`로 원본 ZIP 해제 폴더를 지정하면 복사본과 원본도 비교합니다.
