# 업무 4 B 담당 라벨링 결과 보고서 — P0008~P0010

- 작성일: 2026-08-28
- 작업 브랜치: `data/labeling-v0.1`
- 적용 기준: `dataset/label_guide_v3.1.md`
- 작업 상태: 전사·정규화·라벨링·검증 완료

## 1. 작업 개요

금융감독원 「그놈 목소리」 공개 음성 3건을 직접 전사하고 실제 화자 턴 기준으로 정규화했다. 첫 자동 전사에서 무음 구간이 반복 응답으로 잘못 인식된 부분은 제외하고, 대출 통화의 누락된 앞부분은 재전사해 복원했다.

| source_id | conversation_id | 출처 | conversations | utterances | review |
|---|---|---|---:|---:|---:|
| S018 | P0009 | [전자금융거래법 위반 사건 사칭 통화](https://www.fss.or.kr/fss/bbs/B0000207/view.do?nttId=36729&menuNo=200691&pageIndex=1) | 1 | 20 | 4 |
| S019 | P0010 | [햇살론저축은행 사칭·선입금 요구 통화](https://www.fss.or.kr/fss/bbs/B0000206/view.do?nttId=36735&menuNo=200690&pageIndex=1) | 1 | 105 | 17 |
| S020 | P0008 | [서울중앙지검 수사관 사칭 통화](https://www.fss.or.kr/fss/bbs/B0000207/view.do?nttId=36726&menuNo=200691&pageIndex=1) | 1 | 78 | 11 |
| **합계** | **P0008~P0010** |  | **3** | **203** | **32** |

출처 페이지는 공식 transcript 없이 MP3만 제공하므로 `has_transcript=false`로 기록했다. 이름과 생년월일 등 식별 가능한 부분은 `○○○`으로 마스킹했다. 기존 P0001~P0004 및 N0001 raw 파일은 수정하지 않았다.

## 2. 신규 데이터 통계

### is_phishing

| conversation | `true` | `false` | 합계 |
|---|---:|---:|---:|
| P0008 / S020 | 39 | 39 | 78 |
| P0009 / S018 | 10 | 10 | 20 |
| P0010 / S019 | 54 | 51 | 105 |
| **합계** | **103** | **100** | **203** |

### label별 개수

| label | P0008 | P0009 | P0010 | 신규 합계 |
|---|---:|---:|---:|---:|
| `institution_impersonation` | 14 | 4 | 24 | 42 |
| `personal_information` | 21 | 4 | 11 | 36 |
| `money_transfer` | 0 | 0 | 7 | 7 |
| `threat_pressure` | 5 | 2 | 2 | 9 |
| `secrecy` | 0 | 0 | 0 | 0 |
| `app_installation` | 0 | 0 | 0 | 0 |

복수 라벨을 허용하므로 label 합계는 `is_phishing=true` 개수와 일치하지 않을 수 있다.

## 3. Review Queue

신규 review queue는 총 32건이다.

- P0008 / S020: 11건 — 5, 9, 11, 17, 19, 25, 27, 43, 51, 65, 77
- P0009 / S018: 4건 — 7, 9, 13, 15
- P0010 / S019: 17건 — 1, 3, 9, 11, 33, 43, 52, 53, 57, 59, 63, 69, 71, 75, 80, 100, 104

모든 항목은 `is_phishing=true`, `labels=[]`, `status="needs_review"` 조건으로 저장했다.

## 4. 전체 누적 통계

| 항목 | 결과 |
|---|---:|
| Conversations | 11 |
| Utterances | 346 |
| 피싱 conversation utterances | 220 |
| 정상 conversation utterances | 126 |
| `is_phishing=true` | 119 |
| `is_phishing=false` | 227 |
| `institution_impersonation` | 49 |
| `personal_information` | 41 |
| `money_transfer` | 7 |
| `threat_pressure` | 9 |
| `secrecy` | 0 |
| `app_installation` | 0 |
| Review queue | 48 |

## 5. Validator 결과

```text
Validated conversations: 11
Validated utterances: 346
Errors: 0
Warnings: 0

Validated labeled conversations: 11
Validated labeled utterances: 346
is_phishing=true: 119
is_phishing=false: 227
Review entries: 48
True-without-label review omissions: 0
Errors: 0
Warnings: 0
```

## 6. Label Guide v3.1 개선 제안

1. 개인정보 유출 피해 이력, 통장 양도 이력, 신분증 분실 시점처럼 허위 수사에서 수집하는 사건·행동 이력을 `personal_information`에 포함할지 명시가 필요하다.
2. 카카오톡 친구 추가·사진 전송처럼 앱 설치 없이 외부 채널로 이동시키는 행위를 별도 `channel_migration` 유형으로 관리할지 검토가 필요하다.
3. 허위 대출 한도·금리·상환 조건 설명을 `institution_impersonation`으로 볼 수 있는 직접 수행 기준과 별도 대출빙자 라벨의 필요성을 정리할 필요가 있다.
4. 공증·위임 비용을 안내하는 단계와 실제 송금·수납을 요구하는 단계 사이의 `money_transfer` 경계를 사례로 명문화할 필요가 있다.
5. 사기범의 짧은 확인 응답·모욕·종료 인사를 `is_phishing=true`로 유지할지 예외 처리할지 기준이 필요하다.

## 7. 산출물

- `dataset/raw/phishing/P0008/`
- `dataset/raw/phishing/P0009/`
- `dataset/raw/phishing/P0010/`
- `dataset/staging/phishing_part_임정윤.jsonl`
- `dataset/staging/review_queue_임정윤.jsonl`
- `dataset/metadata/source_registry.csv`
