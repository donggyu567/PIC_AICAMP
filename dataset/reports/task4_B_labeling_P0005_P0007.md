# 업무 4 B 담당 라벨링 결과 보고서 — P0005~P0007

- 작성일: 2026-08-28
- 작업 브랜치: `data/labeling-v0.1`
- 데이터 반영 커밋: `3ff8d83 feat: add FSS phishing labels for P0005-P0007`
- 적용 기준: `dataset/label_guide_v3.1.md`
- 작업 상태: 라벨링 및 검증 완료 / 담당자별 `staging` 제출 규칙 반영

## 1. 작업 개요

금융감독원 「그놈 목소리」 공개 음성 3건을 conversation 단위로 전사·정규화하고, 각 발화를 전체 통화 문맥과 speaker 및 source를 함께 보면서 라벨링했다.

| source_id | conversation_id | 출처 | conversations | utterances |
|---|---|---|---:|---:|
| S005 | P0005 | [금융범죄 수사·사건 유출 시 처벌 사칭 통화](https://www.fss.or.kr/fss/bbs/B0000207/view.do?nttId=36745&menuNo=200691&pageIndex=1) | 1 | 9 |
| S006 | P0006 | [KB저축은행 사칭·휴대전화 정보 확인 통화](https://www.fss.or.kr/fss/bbs/B0000206/view.do?nttId=36744&menuNo=200690&pageIndex=1) | 1 | 20 |
| S007 | P0007 | [검찰 사칭·불법 명의도용 사건 통화](https://www.fss.or.kr/fss/bbs/B0000207/view.do?nttId=36740&menuNo=200691&pageIndex=1) | 1 | 36 |
| **합계** | **P0005~P0007** | **금융감독원 공개 MP3** | **3** | **65** |

출처 페이지는 공식 transcript가 아닌 MP3를 제공하므로 source registry의 `has_transcript`는 `false`로 기록했다. 공개 음성을 직접 전사하고 발화 경계를 정리했으며, 사람 이름 등 식별 가능한 부분은 `○○` 또는 `○○○`으로 마스킹했다. 기존 P0001~P0004 및 N0001 raw 파일은 수정하지 않았다.

## 2. 정규화 및 라벨링 원칙

- P0005~P0007에서는 `speaker_A`를 사기범, `speaker_B`를 통화 상대방으로 일관되게 사용했다.
- `is_phishing`은 발화 단독이 아니라 speaker, 앞뒤 발화, conversation 전체 흐름과 source를 함께 보고 판단했다.
- `labels`는 현재 발화가 직접 표현하거나 수행하는 위험행위에만 부여했다. 앞선 기관 사칭 라벨을 후속 발화에 자동 상속하지 않았다.
- 피해자의 응답, 반문, 거절 및 사기범의 말을 되묻는 발화는 원칙적으로 `is_phishing=false`, `labels=[]`로 처리했다.
- `is_phishing=true`이지만 현재 6개 라벨에 직접 해당하지 않는 발화는 `labels=[]`로 유지하고 review queue에 모두 기록했다.
- 통신사, 휴대전화 제조사, 메신저 사용 여부 및 카카오톡 친구 추가는 앱 설치나 원격제어 실행이 아니므로 `app_installation`을 부여하지 않았다.
- 대출상품 조건이나 대출 한도 설명은 피해자에게 송금·이체·입금을 직접 요구하지 않으므로 `money_transfer`를 부여하지 않았다.
- 제삼자에게 알리지 못하게 하는 요구에는 `secrecy`, 처벌이나 불리한 증거 제출을 이용한 압박에는 `threat_pressure`를 부여했다.

## 3. Conversation별 검수 결과

### P0005 — 수사기관 사칭·비밀 유지·처벌 압박

- 총 9발화
- 사기범 발화 5건은 `is_phishing=true`, 통화 상대방 발화 4건은 `is_phishing=false`
- 검찰 수사와 공문 발송 권한을 가장하는 발화에 `institution_impersonation` 부여
- 현재 위치가 직장인지 자택인지 묻는 발화에 `personal_information` 부여
- 제삼자가 없는 곳으로 이동시키고 다른 사람의 음성이 들리면 안 된다고 하는 발화에 `secrecy` 부여
- 공무집행방해죄, 징역·벌금 및 불리한 증거 제출을 이용한 압박에 `threat_pressure` 부여
- 피해자의 “와서 수사하세요” 발화는 사기범의 수사 표현을 포함하지만 피해자 반응이므로 `false`, `labels=[]`로 유지

### P0006 — KB저축은행 사칭·대출 권유·메신저 전환 시도

- 총 20발화
- `is_phishing=true` 12건, `is_phishing=false` 8건
- KB금융계열사와 KB저축은행을 사칭하는 현재 발화에 `institution_impersonation` 부여
- 성명과 휴대전화 명의 확인 발화에 `personal_information` 부여
- 통신사, 삼성 스마트폰 여부, 카카오톡 사용 여부는 v3.1의 개인정보 확정 대상에 명시되지 않아 review 대상으로 유지
- 카카오톡 친구 추가와 연락 채널 전환은 `app_installation`이 아니므로 무라벨 review 대상으로 유지
- 대출 금리·상환 조건·한도 설명은 직접적인 금전 이전 요구가 아니므로 `money_transfer`를 부여하지 않음

### P0007 — 서울중앙지검 사칭·명의도용 사건 구성

- 총 36발화
- `is_phishing=true` 18건, `is_phishing=false` 18건
- 서울중앙지검 수사관을 자칭하거나 검거·압수·금융감독원 대조 등 수사 권한을 수행하는 발화에 `institution_impersonation` 부여
- 계좌 개설 여부, 본인 명의 확인, 휴대전화·지갑·신분증 분실 여부를 확인하는 발화에 `personal_information` 부여
- 특정인과의 관계 확인은 v3.1의 개인정보 확정 대상에 명시되지 않아 review 대상으로 유지
- 중고나라 사이트 인지 여부 확인은 단순 웹사이트 언급이므로 `app_installation`을 부여하지 않음
- 피해자가 게시물 번호를 요구하며 사실관계를 검증하려는 발화는 모두 `false`, `labels=[]`로 유지

## 4. 신규 데이터 통계

### is_phishing

| 값 | 개수 |
|---|---:|
| `true` | 35 |
| `false` | 30 |
| **합계** | **65** |

### label별 개수

하나의 발화가 여러 위험행위를 직접 수행하면 복수 라벨을 허용하므로 라벨 개수의 합은 `is_phishing=true` 개수와 일치하지 않을 수 있다.

| label | 개수 |
|---|---:|
| `institution_impersonation` | 9 |
| `personal_information` | 8 |
| `secrecy` | 2 |
| `threat_pressure` | 2 |
| `money_transfer` | 0 |
| `app_installation` | 0 |

## 5. Review Queue

신규 review queue는 총 18건이다. 아래 발화는 모두 `is_phishing=true`, `labels=[]`, `status="needs_review"` 조건을 만족한다.

| 대상 발화 | 검토 사유 요약 |
|---|---|
| P0005-6 | 사기범의 확인성 되묻기이지만 현재 6개 위험행위를 직접 수행하지 않음 |
| P0006-2 | 허위 대출상품 조건 설명을 나타내는 확정 라벨이 없음 |
| P0006-3 | 대출 한도·수령 의사 확인이지만 피해자의 송금·이체 요구는 아님 |
| P0006-7 | 통신사 정보가 v3.1의 개인정보 확정 대상에 명시되지 않음 |
| P0006-9 | 휴대전화 제조사·단말 종류가 개인정보 또는 앱 설치로 확정되지 않음 |
| P0006-11 | 카카오톡 사용 여부 확인은 앱 설치 유도가 아님 |
| P0006-13 | 카카오톡 친구 추가·채널 전환에 해당하는 현재 라벨이 없음 |
| P0006-15 | 사기범의 비내용성 반응 발화 |
| P0006-17 | 카카오톡 연락 필요성 설명이지만 설치 유도가 아님 |
| P0006-19 | 피해자의 거절에 대한 사기범의 비내용성 반응 발화 |
| P0007-5 | 통화 가능 여부 확인으로 현재 6개 위험행위를 직접 수행하지 않음 |
| P0007-7 | 후속 질문을 예고하는 진행 발화 |
| P0007-9 | 특정인과의 관계 정보가 개인정보 확정 대상에 명시되지 않음 |
| P0007-11 | 앞선 관계 질문을 되묻는 진행 발화 |
| P0007-27 | 사건 설명을 예고하는 진행 발화 |
| P0007-29 | 단순 웹사이트 인지 여부 확인은 앱 설치가 아님 |
| P0007-33 | 피해자의 질문에 대한 사기범의 비내용성 반응 발화 |
| P0007-35 | 허위 매물 설명이지만 현재 6개 위험행위를 직접 요구하지 않음 |

## 6. 전체 데이터 누적 통계

P0001~P0007과 N0001을 합친 누적 현황이다.

| 항목 | 결과 |
|---|---:|
| Conversations | 8 |
| Utterances | 118 |
| `is_phishing=true` | 51 |
| `is_phishing=false` | 67 |
| `institution_impersonation` | 16 |
| `personal_information` | 13 |
| `secrecy` | 2 |
| `threat_pressure` | 2 |
| `money_transfer` | 0 |
| `app_installation` | 0 |

## 7. Validator 및 무결성 검증

기존 validator 실행 결과:

```text
Validated conversations: 8
Validated utterances: 118
Errors: 0
Warnings: 0
```

추가 검증 결과:

- JSON 구조 오류: 0
- 중복 `conversation_id + utterance_id`: 0
- `is_phishing=false`인데 labels가 있는 오류: 0
- 허용되지 않은 label: 0
- raw/staging 필드 불일치: 0
- `is_phishing=true + labels=[]` 발화의 review queue 누락: 0

## 8. Label Guide v3.1 후속 개선 제안

이번 파일럿에서 다음 경계가 반복적으로 review queue에 들어갔다. 기존 6개 라벨을 임의로 확장하지 않았으며, 다음 가이드 개정 시 명시적으로 합의할 필요가 있다.

1. **기기·통신 정보 범위**  
   통신사, 휴대전화 제조사, 운영체제, 단말 종류 및 메신저 사용 여부를 `personal_information`에 포함할지, 별도 `device_information` 유형으로 둘지 정의가 필요하다.

2. **메신저 채널 전환**  
   카카오톡 친구 추가, 텔레그램 이동, 오픈채팅 입장처럼 설치 없이 사기 채널로 옮기는 행위를 `app_installation`과 분리한 `channel_migration` 유형으로 관리할지 검토가 필요하다.

3. **허위 대출상품 권유**  
   금리, 상환 조건, 한도와 생활자금 등을 제시해 신뢰를 형성하는 대출빙자형 발화는 현재 `money_transfer` 이전 단계라 확정 라벨이 없다. `fraudulent_loan_offer`와 같은 별도 유형의 필요성을 검토할 수 있다.

4. **비내용성 사기범 발화 처리**  
   “예?”, “네?” 같은 짧은 반응도 피싱 conversation의 사기범 발화라는 이유로 `is_phishing=true`, `labels=[]` 및 review queue에 포함되고 있다. 학습 목적에 따라 이를 유지할지, `is_phishing` 판정 예외로 둘지 기준이 필요하다.

5. **금전 이전 설명과 직접 유도의 경계**  
   제삼자의 입금 피해를 사건 설명으로 언급하는 발화와 현재 통화 상대방에게 송금·이체를 직접 요구하는 발화를 구분한다는 기준을 `money_transfer` 항목에 명문화할 필요가 있다.

6. **전사 신뢰도 메타데이터**  
   공식 transcript 없이 공개 음성을 직접 전사하는 데이터에는 `transcription_method`, `transcription_confidence`, `needs_audio_review` 같은 메타데이터를 별도로 관리하는 방안을 검토할 수 있다.

## 9. 산출물

- `dataset/metadata/source_registry.csv`
- `dataset/raw/phishing/P0005/`
- `dataset/raw/phishing/P0006/`
- `dataset/raw/phishing/P0007/`
- `dataset/staging/phishing_part_임정윤.jsonl`
- `dataset/staging/normal_part_임정윤.jsonl`
- `dataset/staging/review_queue_임정윤.jsonl`
- `dataset/label_guide_v3.1.md`
