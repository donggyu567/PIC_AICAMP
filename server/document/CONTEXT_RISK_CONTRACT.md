# LLM 발화 보정·문맥 위험 판단 통합 계약

갱신: 2026-11-03. 기존의 보정 → AI → 별도 문맥 판단 순서를 대체한다.

## 1. 역할과 실행 순서

```text
마스킹된 현재 발화 + 같은 통화의 이전 발화 전체
 → OpenAI 한 번 호출: 현재 문장 보정 + 문맥 판단
 → 응답·마스킹 토큰·근거 ID 검증
 → 서버가 보정 문장을 .pt AI로 전달
 → 최근 20개 누적 계산·기존 경고 → 함께 저장·응답
```

LLM이 AI 도구를 호출하는 구조가 아니다. 서버가 검증된 `corrected_text`를 기존 AI 어댑터에 전달한다. LLM에는 아직 계산 전인 현재 위험 점수·누적 점수·AI 모델 버전을 보내지 않는다. 판단 대상은 문장과 통화 흐름이다. `.pt` AI는 현재 문장과 이전 최대 5개 발화를 사용한다.

## 2. 입력과 출력

`context_service.prepare_utterance()`가 같은 통화의 저장 기록과 현재 마스킹 입력으로 `ContextRiskInput`을 구성한다. 현재 발화가 마지막이며 과거 발화는 저장된 분석용 문장이다. 통화 ID는 OpenAI 요청에서 제외하고 발화 번호만 근거 참조에 사용한다.

```json
{
  "current_utterance_id": 2,
  "utterances": [
    {"utterance_id": 1, "text": "수사기관입니다."},
    {"utterance_id": 2, "text": "안전 계좌 [ACCOUNT_NUMBER]로 이체하세요."}
  ]
}
```

OpenAI 출력은 `PreparedUtterance`다.

```json
{
  "corrected_text": "안전 계좌 [ACCOUNT_NUMBER]로 이체하세요.",
  "context_judgment": {
    "assessment": "suspicious",
    "reason": "기관 사칭 이후 안전 계좌로의 송금을 요구합니다.",
    "evidence_utterance_ids": [1, 2],
    "risk_types": ["institution_impersonation", "money_transfer"]
  }
}
```

- `corrected_text`는 현재 발화만 반환한다. 문장부호·띄어쓰기·명확한 오타만 최소 수정하고 불확실하면 입력을 유지하도록 지시한다.
- 부정·금지·인용·예방교육·행동 요구의 의미를 보존하고, 위험 판단에 맞춰 문장을 강화하지 않도록 지시한다. 의미 보존의 정확성까지 코드 검증으로 보장하는 것은 아니다.
- 기존 `validate_masking_token_preservation()`으로 마스킹 토큰의 종류·개수·순서를 확인한다. 문장 길이·형식·근거 번호도 외부 응답 경계에서 검사한다. 위험 판단 `suspicious`에는 입력에 존재하는 근거 발화가 필요하다.
- `assessment`는 `suspicious` / `no_clear_risk` / `insufficient_context`다. `no_clear_risk`는 안전 보증이 아니다.

## 3. 실패와 재시도

| 상황 | 보정 상태 | 문맥 상태 | AI 입력·처리 |
|---|---|---|---|
| 통합 LLM 성공 | `ok` | `ok` | 검증된 보정 문장 |
| 호출·응답·토큰·근거 검증 실패 | `fallback` | `error` | 통합 출력을 버리고 원래 마스킹 입력 사용 |
| `PIC_CONTEXT_MODEL` 미설정 | `fallback` | `not_run` | 마스킹 입력으로 AI만 실행 |
| LLM 성공 후 AI 실패 | `ok` | `ok` 유지 | AI 점수 null, `analysis_status=error` |

입력 마스킹 계약 위반은 422로 차단하며 LLM 실패 우회의 대상이 아니다. 통합 LLM 실패 시 다른 보정 API로 재호출하지 않는다. 이전 발화의 문맥 판단을 현재 결과로 복사하지 않는다.

`/analyze/retry`는 마지막 AI 실패만 복구한다. 같은 발화의 저장된 문장·보정 상태·문맥 판단을 그대로 보존하고 OpenAI는 다시 호출하지 않는다. 실패한 LLM만 별도 재시도하는 API는 없다. 새 발화에서는 새 문맥 판단을 실행한다.

## 4. 앱 응답·저장·경고

기존 응답 JSON과 저장 스키마를 유지한다. `current_text`에는 실제 AI 입력, `correction_status`에는 보정 상태, `context_judgment`에는 실행 상태·모델·판단을 넣는다. `ok`는 보정문이 반드시 변경됐다는 의미가 아니라 통합 응답 검증 성공을 뜻한다.

`context_judgment`의 외부 형식은 기존 `{status, model, result}`다. AI 성공 여부와 독립적으로 판단 상태를 읽는다. 결과 조회와 종료의 `last_analysis`에도 동일하게 보존한다. 과거 기록에서 필드가 없으면 `not_run`으로 읽는다.

기존 AI 점수 기반 경고·알림은 유지한다. LLM 판단으로 AI 경고를 하향·해제하거나 새 경고 이벤트를 추가하지 않는다. 통화 잠금과 기존 계산·파일 저장을 재사용하며 한 번의 저장으로 두 결과를 함께 보존한다.

## 5. 설정과 시간 측정

- `OPENAI_API_KEY`, `PIC_CONTEXT_MODEL`로 단일 호출을 설정한다. 루트 `.env`를 자동으로 읽고 명시적 환경변수가 우선한다. 기존 `OPENAI_MODEL`은 기존 backend 보정용이며 새 서버의 통합 경로에서는 사용하지 않는다.
- 추론 강도는 `reasoning.effort="low"`다. `service_tier="fast"`로 Fast 처리를 명시 요청한다. 실제 반환 등급은 `LLM_USAGE` 로그로 확인하며 Fast가 적용됐다고 요청 설정만으로 단정하지 않는다. 설명 500자·출력 2,048토큰 한도는 유지한다.
- `server/lifespan.py::lifespan()`에서 `create_llm_client()`로 클라이언트를 한 번 만들고 요청에서 재사용하며 종료 시 닫는다. 키 또는 모델이 없으면 클라이언트를 만들지 않는다. 키·모델을 변경하면 서버를 재시작한다.
- 기존 Responses API·Structured Outputs 방식을 재사용한다. `store=False`, `truncation="disabled"`, 타임아웃 10초, 자동 재시도 0회, 최대 출력 2,048토큰이다. 미완료·거부 응답은 실패로 처리한다.
- 누적 문맥을 임의로 자르거나 요약하지 않는다. 입력 한도 초과 시 위의 실패 규칙을 따른다. 공급자 보관 정책과 서버의 저장 옵션은 별개다.
- 시간은 `llm_preparation`, `ai_inference`, `calculation_warning`, `save`, `total` 등으로 `Server-Timing` 헤더와 로그에 기록한다. 통합 호출이므로 보정과 문맥 판단 각각의 내부 추론 시간은 분리할 수 없다.

## 6. 검증 범위

새 서버 분석 7개, 라이프사이클 4개, 기존 backend 통합 분석 10개로 총 21개 테스트를 통과했다. 호출 1회·AI 입력 전달·기록 조회/저장·실패 시 대체 입력·마스킹 보호·AI 재시도 보존을 확인했다. 실제 호출 시간과 검증 한계는 [서버 README](../README.md)에 기록한다. 모델 정확도와 앱 표시는 별도 확인 대상이다.

참고: [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs).
