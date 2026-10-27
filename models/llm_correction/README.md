# Masked STT Correction

이 모듈은 태블릿의 로컬 NER 결과를 Python 보정 단계가 안전하게 받고,
LLM으로 보정하고 결과를 저장해 업무 3 문맥 관리 단계에 전달하기 위한
계약과 핵심 처리 기능을 제공합니다.

현재 모듈에는 데이터 계약, 공급자 독립적인 LLM 보정 엔진, OpenAI Responses
API 어댑터와 보정 결과 저장 기능이 포함됩니다. 태블릿용 HTTP API 엔드포인트와
업무 3 문맥 관리 코드의 실제 연결은 별도의 통합 단계에서 추가해야 합니다.

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

## OpenAI 공급자 연결

이 프로젝트의 기본 모델은 짧은 한국어 STT 보정처럼 비용과 처리량이 중요한
작업에 맞춰 `gpt-5.6-luna`로 정했습니다. 모델은 환경변수로 교체할 수 있으므로
실제 마스킹 STT 평가에서 품질이 부족할 때만 더 큰 모델과 비교합니다.

의존성을 설치하는 명령은 다음과 같습니다. 이 저장소에는 설치 명령만 기록하며,
라이브러리 코드가 패키지를 자동 설치하지 않습니다.

```powershell
python -m pip install -r requirements.txt
```

실제 키는 저장소 파일에 기록하지 않고 실행 환경의 `OPENAI_API_KEY`로
주입합니다. `.env.example`은 변수 이름을 알려 주는 예시일 뿐이며 이 모듈이
`.env` 파일을 자동으로 읽지는 않습니다.

```text
OPENAI_API_KEY       필수, 프로젝트 관리자가 발급한 서버용 비밀 키
OPENAI_MODEL         선택, 기본값 gpt-5.6-luna
OPENAI_TIMEOUT_SECONDS 선택, 기본값 10
OPENAI_MAX_RETRIES   선택, 기본값 2
OPENAI_MAX_OUTPUT_TOKENS 선택, 기본값 32768
```

기본 출력 한도 32,768토큰은 보정 엔진이 허용하는 최대 10,000자 입력도 중간에
잘리지 않도록 둔 상한입니다. 한도를 크게 설정했다고 그만큼 고정 과금되는 것은
아니며 실제 생성된 토큰 수를 기준으로 과금됩니다.

```python
from models.llm_correction import CorrectionEngine, OpenAIResponsesClient

client = OpenAIResponsesClient()
engine = CorrectionEngine(client)
result = engine.correct(masked_transcript)
```

`OpenAIResponsesClient`는 Responses API를 `store=False`,
`reasoning.effort=none`, strict JSON Schema로 호출합니다. 요청에는 엔진이 만든
시스템 프롬프트와 `masked_text`가 든 사용자 프롬프트만 들어가며,
`conversation_id`, `utterance_id`, 마스킹 복원 정보, 사용자 식별자, 도구와
대화 상태는 보내지 않습니다. OpenAI의 기본 악용 모니터링 로그 보관과
`store=False`는 서로 다른 정책이므로 완전한 무보관이 필요하면 조직 계정의
Zero Data Retention 승인 여부를 별도로 확인해야 합니다.

공급자 호출 실패, 미완료 응답과 빈 응답은 원래 SDK 오류나 입력 내용을
노출하지 않는 `LLMClientError`로 바꿉니다. 모델의 `refusal` 내용도 결과나
오류에 포함하지 않습니다. 정상 문자열도 기존 엄격 파서와 계약 검증을
통과해야만 `CorrectionResult`가 됩니다.

`tests/test_openai_client.py`는 실제 API 키나 네트워크를 사용하지 않고 가짜
SDK 응답으로 요청 옵션과 오류 처리를 검사하는 단위 테스트 파일입니다. 실제
OpenAI 호출은 과금과 외부 전송이 발생하므로 이 테스트 파일에는 넣지 않습니다.

다른 공급자로 교체할 때는 다음 인터페이스를 구현하면 됩니다.

```python
class MyLLMClient:
    def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        # 공급자 SDK를 호출하고 모델의 문자열 응답만 반환합니다.
        ...

engine = CorrectionEngine(MyLLMClient())
result = engine.correct(masked_transcript)
```

## 보정 결과 저장

`CorrectionResultStore`는 검증된 결과를 UTF-8 JSON 파일로 저장합니다.
저장 위치는 호출자가 반드시 지정하므로 모듈이 임의의 운영 경로에 파일을
만들지 않습니다.

```python
store = CorrectionResultStore("outputs")

existing = store.load(masked_transcript)
if existing is not None:
    result = existing
else:
    result = engine.correct(masked_transcript)
    output_path = store.save(result)
```

파일 경로는 다음 규칙을 사용합니다.

```text
<output_root>/conversation-<conversation_id의 SHA-256>/tuned_result0017.json
```

- `conversation_id`는 JSON에는 원래 값으로 저장하지만 파일 경로에는 직접
  넣지 않습니다. `/`, `\\`, `..` 같은 값으로 저장 루트를 벗어나는 것을
  방지하기 위해 고정 길이 SHA-256 폴더명을 사용합니다.
- 파일명은 `tuned_result{utterance_id:04d}.json`입니다. 네 자리는 최소
  너비이므로 발화 ID가 10,000 이상이어도 잘리지 않습니다.
- 임시 파일을 완전히 기록하고 `fsync`한 뒤, 기존 파일을 덮어쓰지 않는
  방식으로 최종 경로에 게시합니다.
- 동일한 결과를 다시 저장하면 기존 경로를 반환합니다. 같은 통화 ID와
  발화 ID에 다른 결과가 있으면 `CorrectionOutputConflictError`를 발생시키고
  기존 파일을 보존합니다.
- 멱등성 키는 합의된 `(conversation_id, utterance_id)`입니다. `load()`는 같은
  키의 파일이 있으면 기존 결과를 반환하므로, 클라이언트는 서로 다른 발화에
  한 번 사용한 `utterance_id`를 다시 사용하면 안 됩니다.
- 저장된 파일이 손상됐거나 계약을 위반하면 자동으로 덮어쓰지 않습니다.
- `load()`를 LLM 호출 전에 사용해야 중복 요청의 모델 호출 비용도 막을 수
  있습니다.
- 원자적인 create-if-absent 게시에는 하드 링크를 사용하므로 `output_root`는
  NTFS, ext4처럼 하드 링크를 지원하는 로컬 파일 시스템에 두어야 합니다.
  최종 파일 게시 후 임시 링크 정리만 실패한 경우에는 완성된 최종 경로를
  성공 결과로 반환합니다.

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

업무 3에는 OpenAI의 원응답, 프롬프트 또는 API 키를 전달하지 않습니다. 업무 2의
엔진과 계약 검증을 모두 통과한 `CorrectionResult.to_dict()`의 다음 7개 필드만
전달합니다.

```text
schema_version
conversation_id
utterance_id
tuned_text
is_tuned
has_unclear
unclear_segments
```

현재 업무 3 코드는 아래 5개 보정 필드는 처리하지만 `conversation_id`와
`schema_version`을 문맥 결과까지 보존하지 않습니다. 업무 3의 스키마와 문맥
저장소는 두 필드를 추가하고 `(conversation_id, utterance_id)` 단위로 통화를
분리해야 합니다. 업무 2 오류 시 `raw_text` 또는 검증 전 모델 응답으로 대신
처리해서도 안 됩니다.

파일로 연결한다면 업무 3은 `CorrectionResultStore.save()`가 반환한 정확한
`tuned_resultNNNN.json` 경로를 받아야 합니다. 통화 폴더 이름은 개인정보와
경로 조작을 막기 위해 `conversation_id`의 SHA-256 값으로 만들어지므로 업무 3이
원래 ID로 파일 경로를 임의 조합하면 안 됩니다.
