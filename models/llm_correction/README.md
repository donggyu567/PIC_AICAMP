# STT Correction Contract

이 모듈은 태블릿의 로컬 NER 결과를 Python 보정 단계가 안전하게 받고,
업무 3 문맥 관리 단계에 전달하기 위한 데이터 계약을 정의합니다.

이번 단계에는 LLM 호출이나 HTTP API 엔드포인트가 포함되지 않습니다.

## 입력 계약

```json
{
  "schema_version": "1.0",
  "conversation_id": "C0001",
  "utterance_id": 17,
  "masked_text": "[PERSON] 씨 지금 [ACCOUNT_NUMBER] 계좌로 송금하세요.",
  "has_masked_data": true,
  "masked_types": ["PERSON", "ACCOUNT_NUMBER"]
}
```

- `raw_text`는 서버 입력으로 허용하지 않습니다.
- `utterance_id`는 통화 안에서 1부터 증가하는 양의 정수입니다.
- `has_masked_data`는 실제 마스킹 토큰 존재 여부와 같아야 합니다.
- `masked_types`는 문장에 들어 있는 마스킹 토큰 종류와 같아야 합니다.
- 아래 목록에 없는 대괄호 토큰은 개인정보 누락 가능성을 막기 위해 거부합니다.

허용되는 마스킹 토큰은 다음과 같습니다.

```text
[PERSON]
[PHONE_NUMBER]
[ACCOUNT_NUMBER]
[RRN]
[OTP]
[ADDRESS]
```

## 출력 계약

```json
{
  "schema_version": "1.0",
  "conversation_id": "C0001",
  "utterance_id": 17,
  "tuned_text": "[PERSON] 씨, 지금 [ACCOUNT_NUMBER] 계좌로 송금하세요.",
  "is_tuned": true,
  "has_unclear": false,
  "unclear_segments": []
}
```

- 보정 결과는 입력과 같은 `schema_version`, `conversation_id`,
  `utterance_id`를 사용해야 합니다.
- LLM은 입력의 마스킹 토큰을 추가, 삭제, 변경하거나 순서를 바꾸면 안 됩니다.
- 확실하게 고칠 수 없는 부분은 `[불명확]`으로 바꾸고 원문 조각을
  `unclear_segments`에 같은 순서로 기록합니다.
- `is_tuned`는 다음 보정 단계에서 입력 문장과 출력 문장을 비교해 결정합니다.

`validate_correction_against_input()`은 입력과 출력의 버전, 통화 ID,
발화 ID, 마스킹 토큰 순서, `is_tuned` 값과 불명확 원문 조각의 순서를
한 번에 검증합니다.

현재 마스킹 토큰에는 번호가 없으므로 한 발화에 같은 유형의 개인정보가
여러 개 있을 때 서버에서 각각을 구분하거나 복원하지 않습니다. 복원이
필요해지면 `[PERSON_1]` 같은 새 규격을 다음 `schema_version`으로 정의해야 합니다.

## 업무 3 전달

현재 업무 3 코드는 다음 필드를 이미 처리합니다.

```text
utterance_id
tuned_text
is_tuned
has_unclear
unclear_segments
```

`conversation_id`와 `schema_version`이 문맥 결과까지 유지되려면 업무 3의
스키마와 문맥 저장소도 같은 계약으로 갱신되어야 합니다.
