# Voice-phishing AI dataset workspace

## Purpose

보이스피싱 위험 감지 AI 학습을 위한 대화 데이터 수집·정규화·라벨링 작업 공간이다. 원본 데이터와 개인 라벨링 중간 산출물, 검증 완료 후의 최종 병합본을 분리하여 관리한다.

## Current snapshot

2026-08-28 기준으로 다음 데이터가 등록되어 있다.

- 보이스피싱: P0001~P0010, 10 conversations / 285 utterances
- 정상 대화: N0001, 1 conversation / 36 utterances
- 전체: 11 conversations / 321 utterances
- 출처: S001~S007, S018~S020

## Layout

```text
dataset/
|- raw/                    # 사람이 수집한 원본 후보 데이터
|  |- phishing/
|  `- normal/
|- staging/                # 담당자별 라벨링 중간 산출물
|- processed/              # 검증 완료 후 최종 담당자가 만든 병합본
|- examples/               # 스키마 예시
|- metadata/               # 출처 관리표
|- scripts/                # 검증·변환 스크립트
`- README.md
```

## Raw data

원본 데이터는 발화 하나당 JSON 파일 하나로 저장한다.

```text
raw/phishing/P0001/utterance_001.json
raw/normal/N0001/utterance_001.json
```

Raw 파일은 수집 원문과 출처를 보존하며, 라벨링 과정에서 직접 수정하지 않는다. `is_phishing`과 `labels`는 raw 파일에 추가하지 않는다.

### Raw JSON schema

```json
{
  "conversation_id": "P0001",
  "utterance_id": 1,
  "speaker": "speaker_A",
  "text": "Original utterance text",
  "source": "Source name"
}
```

- `conversation_id`는 `^[PN]\\d{4}$` 형식을 사용한다.
- `utterance_id`는 대화별로 1부터 시작하는 양의 정수다.
- `speaker`는 `speaker_A`, `speaker_B`, `unknown` 중 하나다.
- 동일 대화에서 동일 인물의 speaker 값은 일관되게 유지한다.
- 화자를 신뢰성 있게 구분할 수 없으면 `unknown`을 사용한다.
- `text`와 `source`는 비어 있을 수 없다.

## Labeling schema

라벨링할 때는 발화 단독이 아니라 speaker, 앞뒤 문맥, source를 함께 확인한다. 다만 `labels`는 현재 발화가 직접 표현하거나 수행하는 위험행위를 기준으로 부여한다.

```json
{
  "conversation_id": "P0001",
  "utterance_id": 1,
  "speaker": "speaker_A",
  "text": "Original utterance text",
  "source": "Source name",
  "is_phishing": true,
  "labels": ["institution_impersonation"]
}
```

- `is_phishing=false`이면 `labels=[]`이다.
- `is_phishing=true`이면 원칙적으로 하나 이상의 라벨을 부여한다.
- 피싱 진행 발화이지만 현재 라벨 체계에 정확히 해당하지 않으면 억지로 라벨을 붙이지 않고 `labels=[]`로 유지한 뒤 review queue에 기록한다.
- 피해자가 사기범의 말을 되묻거나 반복하는 발화는 원칙적으로 `is_phishing=false`, `labels=[]`로 처리한다.

## 담당자별 staging 산출물

각 담당자는 자신의 결과를 `dataset/staging/`에 JSONL 형식으로 제출한다. JSONL은 한 줄에 JSON 객체 하나를 기록한다.

```text
phishing_part_본인이름.jsonl
normal_part_본인이름.jsonl
review_queue_본인이름.jsonl
```

- `phishing_part_본인이름.jsonl`: 담당한 보이스피싱 대화 전체 발화
- `normal_part_본인이름.jsonl`: 담당한 정상 대화 전체 발화
- `review_queue_본인이름.jsonl`: 추가 검수가 필요한 발화와 사유
- 보이스피싱 대화 안의 피해자 발화도 삭제하지 않고 `is_phishing=false`, `labels=[]` 상태로 포함한다.
- 개인 담당자는 `dataset/processed/`에 직접 병합본을 만들지 않는다.

## Processed data

`dataset/processed/`에는 담당자별 staging 파일을 모두 검증한 후 최종 병합 담당자가 만든 학습용 JSONL만 저장한다. 개인 파일이나 임시 병합본은 저장하지 않는다.

## Source registry

출처를 추가하면 `metadata/source_registry.csv`와 공유드라이브의 `운영관리 / 데이터 관리 표`를 함께 갱신한다.

CSV 필드는 다음과 같다.

```text
source_id, source_name, source_url, data_type,
conversation_count, utterance_count, has_transcript,
usage, status, notes
```

- 출처와 URL, 대화 수, 발화 수, Transcript 제공 여부를 확인하여 기록한다.
- 직접 전사했더라도 원 출처가 Transcript를 제공하지 않았다면 `has_transcript=false`로 기록하고 `notes`에 직접 전사 사실을 남긴다.
- 데이터와 출처표가 모두 갱신되어야 작업 완료로 본다.
- 라이선스와 재배포 조건은 GitHub에 원문을 추가하기 전에 별도로 확인한다.

## Validation

저장소 루트에서 다음 명령을 실행한다.

```bash
python dataset/scripts/validate_raw.py
```

Validator는 `dataset/raw/phishing/`과 `dataset/raw/normal/`을 검사한다. JSON 구문, 필수 필드, 폴더와 ID 일치, 파일명과 utterance ID 일치, 중복 ID, 발화 번호 연속성을 확인한다.

담당자별 staging 산출물은 추가로 다음을 확인한다.

- JSONL 구문과 필수 필드
- conversation ID와 utterance ID 중복
- `is_phishing=false`인데 labels가 존재하는 오류
- `is_phishing=true`, `labels=[]` 발화의 review queue 누락
- raw와 staging의 발화 수 및 원문 일치
