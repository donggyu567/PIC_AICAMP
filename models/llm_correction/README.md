# STT Correction Contract

이 모듈은 태블릿의 로컬 NER 결과를 Python 보정 단계가 안전하게 받고,
업무 3 문맥 관리 단계에 전달하기 위한 데이터 계약을 정의합니다.

현재 모듈에는 데이터 계약과 공급자 독립적인 LLM 보정 엔진이 포함됩니다.
OpenAI 같은 실제 LLM 공급자 SDK 연결과 HTTP API 엔드포인트는 다음 통합
단계에서 추가합니다.

## 보정 처리 흐름

```text
MaskedTranscript
    -> masked_text만 프롬프트에 직렬화
    -> LLMClient.complete(...)
    -> JSON 응답 엄격 파싱
    -> is_tuned / has_unclear를 Python에서 계산
    -> 입력과 결과의 ID 및 마스킹 토큰 검증
    -> CorrectionResult
```

- `conversation_id`, `utterance_id`, `schema_version`, `masked_types`는 LLM에
  보내지 않습니다.
- LLM은 `tuned_text`, `unclear_segments` 두 필드만 결정할 수 있습니다.
- 설명문, Markdown 코드 블록, 중복 키 또는 추가 필드가 포함된 응답은
  `LLMResponseError`로 거부합니다.
- 모델 응답은 최대 20,000자, `tuned_text`는 최대 10,000자,
  `unclear_segments`는 최대 100개(각 1,000자)로 제한합니다.
- `masked_text`도 최대 10,000자로 제한하며, 초과하면 외부 LLM을 호출하지
  않습니다. 이 상한은 업무 1 및 API 담당자와 최종 합의가 필요합니다.
- 공급자 장애는 원래 SDK 오류 내용을 노출하지 않는 `LLMClientError`로,
  잘못된 JSON 응답은 `LLMResponseError`로, 계약 검증에 실패한 보정은
  `CorrectionValidationError`로 변환합니다. 오류에는 입력이나 모델 응답을
  넣지 않으며, 어느 경우에도 임의의 보정 결과로 대체하지 않습니다.

실제 공급자 연결 클래스는 다음 인터페이스를 구현하면 됩니다.

```python
class MyLLMClient:
    def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        # 공급자 SDK를 호출하고 모델의 문자열 응답만 반환합니다.
        ...

engine = CorrectionEngine(MyLLMClient())
result = engine.correct(masked_transcript)
```

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

현재 검증은 마스킹 토큰이 입력과 같은 개수와 순서로 남았는지 확인합니다.
문장 안에서 토큰 하나가 주변 단어보다 앞이나 뒤로 이동했는지까지 증명하려면
문자 위치 또는 편집 연산을 포함하는 새 계약이 필요합니다. `[불명확]`도 지정한
원문 조각이 사라졌는지는 검사하지만 정확히 같은 위치에서 바뀌었는지까지는
현재 계약만으로 증명할 수 없습니다. 또한 서버 계약은 `masked_text` 안에 NER가
놓친 개인정보가 있는지 판별하지 못하므로, 태블릿은 로컬 NER가 성공한 발화만
전송해야 합니다.

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
