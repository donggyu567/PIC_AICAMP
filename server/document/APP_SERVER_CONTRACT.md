# 앱 ↔ 새 서버 연결 계약

갱신: 2026-10-30. 대상은 `server.main:app`이며 기존 `backend.main:app`과 구분한다.

현재 서버 구현 범위는 **STT 중계, 마스킹 발화 분석·AI 재시도, 문맥 판단 저장·응답, 결과 조회·알림 조회/수신확인·통화 종료 API**다. API 흐름은 대체 객체로 확인했다. 임시 체크포인트의 CPU 로딩·샘플 추론은 별도로 확인했지만 실제 외부 API·모델·Android를 결합한 전체 흐름은 미검증이다. 사용자 요청으로 STT 실연결·앱 작업은 보류하고 서버 작업을 진행한다. 철회·삭제 API는 아직 없다.

## 1. 연결 주소와 기본 규칙

**2026-11-07 서버 변경:** 새 서버 코드는 STT WebSocket과 발화·통화·알림 API에 `Authorization: Bearer <기기 토큰>`을 요구한다. 토큰 없이 연결하면 거절되며, 발급 기기만 그 기기의 STT에서 생성된 통화에 접근할 수 있다. 다른 기기나 소유권이 없는 통화는 404다. Android 토큰 저장·전송은 아직 미구현이므로 기존 앱은 변경된 서버와 연결되지 않는다. 기존 테스트 데이터·통화의 소유권 이전도 아직 없다. 이전 문서의 인증 없이 사용 가능한 예시는 후속 Android 연결 전까지 적용되지 않는다.

**Android 후속 연결:** 새 앱은 운영자가 발급한 토큰을 Android Keystore로 암호화해 보관하고 등록한 서버 출처의 STT WebSocket·발화·종료·철회 요청에 전송한다. HTTP 통신은 debug 빌드에서 로컬 개발 주소에만 허용하고, 그 외에는 HTTPS/WSS가 필요하다. 관련 단위 테스트와 빌드는 통과했으나 실제 휴대폰·서버 연결과 기존 통화 이전은 확인되지 않았다. 위 단락 중 Android 미구현이라는 설명은 이 후속 기록으로 대체한다.

**실기기 확인:** 사용자가 USB 연결된 Android에서 기기 토큰 등록 후 위험 점수와 최종 결과 표시를 확인했다. 인증 없는 결과 조회는 401이었다. 타 기기 인증 차단은 단위 테스트로 확인했으며 실제 기기·기존 통화 이전·TLS 배포는 미검증이다.

**요청 제한:** 시연 초기값으로 기기별 분석·재시도는 합쳐서 60초에 30회, 동시 STT는 기기당 2개·서버 전체 20개까지 허용한다. 같은 접속 주소에서 인증 실패가 60초에 30회 누적되면 일시 차단한다. HTTP 제한 초과는 429와 `Retry-After: 60`을 반환한다. 초과한 STT 연결은 수락 전에 거부한다. 앱은 분석 실패 후 발화 번호를 유지하고 결과 확인·재시도를 사용한다. 서버 재시작 시 제한 상태가 초기화되며 프록시 환경의 실제 접속 주소 처리는 배포 시 확인해야 한다.

- 경로: `WS /api/v1/stt`
- 개발 PC에서 실행한 경우: `ws://127.0.0.1:8000/api/v1/stt`
- Android의 `127.0.0.1`은 기기 자신이다. 에뮬레이터는 호스트 접근 주소, 실기기는 개발 PC의 접근 가능한 주소를 사용한다. 배포 시에는 HTTPS/WSS 주소를 사용한다.
- Swagger `/docs`의 Execute로 WebSocket을 테스트할 수 없다.
- 제어·응답은 UTF-8 JSON 텍스트 메시지, 음성은 바이너리 메시지다.
- 한 연결은 한 시연 세션이다. 서버가 `conversation_id`를 생성한다. 재접속 시 새 ID가 발급되며 이전 세션 자동 복구는 지원하지 않는다.
- ElevenLabs API 키는 서버 환경변수에만 둔다. 앱 요청에 API 키를 넣지 않는다.

## 2. 앱 → 서버

### 시작

연결 후 10초 안에 첫 텍스트 메시지를 보낸다. 앱은 먼저 데이터 전송 동의와 마이크 권한을 확인한다. 아래 형식의 모든 필드가 필요하고 정의하지 않은 필드는 거부한다.

```json
{"type":"start","consent":true,"audio_format":"pcm_s16le","sample_rate":16000,"channels":1}
```

`consent=false`는 허용하지 않는다. 이 값은 앱이 동의를 확인했다는 선언이며, 서버가 실제 동의 화면을 구현하거나 확인했다는 뜻은 아니다. 같은 연결에서 `start`를 다시 보내면 오류다.

### 음성

`ready`를 받은 뒤부터 보낸다. 앱은 준비 완료 전에 음성을 보내거나 미리 모은 음성을 한꺼번에 재생하듯 전송하지 않는다.

| 항목 | 값 |
|---|---|
| 인코딩 | signed 16-bit little-endian PCM |
| 샘플레이트 / 채널 | 16,000Hz / 모노 |
| 헤더 | WAV 등 파일 헤더 없음 |
| 메시지 | WebSocket 바이너리 프레임, Base64 JSON 아님 |
| 권장 크기 | 100ms = 3,200바이트 |
| 허용 크기 | 2~32,000바이트, 2의 배수 |

서버는 바이트 길이를 검사한다. 실제 인코딩·샘플레이트 변환은 앱 책임이다. 앱은 말하지 않는 구간도 마이크의 무음 PCM을 실시간 속도로 보내며, 전송 대기열을 무한히 쌓지 않는다. 중계는 최대 5초 분량마다 확정을 요청하고 응답을 기다리므로 일시적인 전송 지연이 생길 수 있다. Android 연결 단계에서 실제 지연을 확인한다.

### 입력 종료

앱은 새 마이크 수집을 멈추고 마지막 음성 청크 뒤에 아래 텍스트 메시지를 보낸다.

```json
{"type":"stop"}
```

그 뒤 새 음성을 보내지 않고 `transcript`와 `stopped` 또는 `error`를 기다린다. 바로 소켓을 닫으면 마지막 결과가 유실될 수 있다. `stop` 이후 들어온 추가 입력은 처리 대상이 아니며, 서버는 남은 발화를 마무리하고 닫는다.

## 3. 서버 → 앱

### 준비 완료

```json
{"type":"ready","conversation_id":"서버가-발급한-UUID","max_session_seconds":600}
```

ElevenLabs의 `session_started`를 확인한 뒤 전송한다. 앱은 이 ID를 현재 시연에 보관하고 이후 마스킹·분석 연결에도 동일하게 사용할 예정이다.

### 처리 상태

```json
{"type":"status","conversation_id":"서버가-발급한-UUID","status":"recognizing"}
```

- `recognizing`: 인식 중. 중간 원문은 포함하지 않는다. 같은 상태가 여러 번 올 수 있다.
- `finalizing`: 입력을 마치고 남은 확정 결과를 받는 중. 앱은 음성 전송을 중단한다.
- 상태 변화만으로 화면의 위험 점수를 바꾸지 않는다.

### 확정 텍스트

```json
{"type":"transcript","conversation_id":"서버가-발급한-UUID","utterance_id":1,"text":"안녕하세요."}
```

- `text`는 **마스킹 전 확정 원문**이다. 앱은 메모리에서 마스킹한 뒤에만 화면 표시·기록·후속 분석 전송을 한다.
- `utterance_id`는 해당 세션에서 1부터 순서대로 증가한다. 빈 확정 결과는 전달하지 않고 번호도 증가시키지 않는다.
- 같은 내용을 다시 말하면 서로 다른 번호의 발화로 전달한다. 텍스트가 같다고 제거하지 않는다.
- 공급자의 부분 결과는 이 메시지로 변환하지 않는다.
- 현재 확정 단위는 최대 5초의 음성 구간이다. 완전한 문장 경계나 화자 구분을 보장하지 않는다.
- 앱은 `(conversation_id, utterance_id)`로 발화를 구분하고, 이전 시연·철회된 시연의 결과를 현재 화면에 반영하지 않는다.

### STT 종료 완료

```json
{"type":"stopped","conversation_id":"서버가-발급한-UUID","reason":"user_stop","last_utterance_id":1}
```

- `reason`: `user_stop` 또는 `time_limit`.
- `last_utterance_id`: 마지막으로 전달한 번호. 텍스트가 없으면 0.
- 일반 종료 시에는 마지막 확정 응답을 처리한 뒤 `stopped`, 이후 WebSocket close 1000을 보낸다.
- 600초는 `ready` 이후 서버 음성 수신 구간의 시간 제한이다. 진행 중인 확정 요청·마지막 결과 대기는 추가 시간이 걸릴 수 있다. 앱도 10분에 수집을 중단해야 하며, 서버 제한 이후 도착한 음성은 처리하지 않는다.
- **STT 종료이지 전체 분석 완료가 아니다.** 앱은 이미 받은 발화의 마스킹·분석 응답을 확인한 뒤 9절의 HTTP 종료 API로 종료를 확정한다.

### 오류

```json
{"type":"error","conversation_id":null,"code":"stt_unavailable","message":"음성 인식 서비스에 연결할 수 없습니다."}
```

| code | 의미 | 앱 처리 |
|---|---|---|
| `invalid_message` | 제어 JSON·필드 오류 또는 시작 요청 시간 초과 | 수집 중단, 요청 형식 확인 |
| `invalid_audio` | 음성 크기·샘플 정렬 오류 | 수집 중단, PCM 형식 확인 |
| `invalid_state` | 시작 전 음성/종료, 중복 시작 | 수집 중단, 전송 순서 확인 |
| `stt_unavailable` | 키 누락, 공급자 접속·인증·시작 실패 | 수집 중단, 오류 안내 |
| `stt_failed` | 공급자 연결 끊김·응답 오류 | 수집 중단, 현재 세션 미완료 표시 |
| `finalization_timeout` | 요청한 발화 확정 응답이 10초 내에 없음 | 마지막 성공 결과 유지, 미완료 표시 |

`conversation_id`는 아직 생성되지 않았으면 null이다. 공급자 오류 원문이나 API 키는 전달하지 않는다. 입력 오류는 close 1008, 서비스 오류는 close 1011로 닫는다. `error` 뒤에 성공한 `stopped`는 보내지 않는다. 네트워크 단절로 오류 메시지를 못 받은 경우도 정상 완료로 취급하지 않는다.

최초 공급자 접속의 일시적 네트워크 실패만 음성 전송 전에 1회 재시도한다. 스트리밍 중 실패한 음성은 저장·자동 재전송하지 않는다. 사용자가 재시도하면 새 연결·새 세션으로 시작하며, 이전 시연 결과와 섞지 않는다.

## 4. 앱 처리 순서

```text
동의·마이크 권한 확인 → WebSocket 연결 → start
 → ready 수신 → 실시간 PCM 전송
 → status: 처리 상태 표시
 → transcript: 기기 내 마스킹 → 마스킹된 문장 표시
 → 같은 ID로 서버 위험 분석 요청
 → 종료 버튼: 수집 중단 → 마지막 청크 → stop
 → 마지막 transcript → stopped
 → 처리 중인 위험 분석까지 반영 → HTTP 통화 종료 → 최종 화면 확정
```

일반 종료와 동의 철회는 다르다. 철회 시에는 수집·전송을 중단하고 STT 연결을 닫아 후속 원문을 받지 않는다. 기록 삭제와 철회 상태 저장 API는 이후 단계에서 연결한다.

## 5. 마스킹 발화 분석 HTTP API

`POST /api/v1/utterances/analyze`

```json
{
  "schema_version": "1.0",
  "conversation_id": "ready에서 받은 ID",
  "utterance_id": 1,
  "masking_status": "succeeded",
  "masked_text": "[PERSON]입니다.",
  "has_masked_data": true,
  "masked_types": ["PERSON"]
}
```

- 마스킹을 실행해 성공한 경우만 보낸다. 개인정보가 발견되지 않았다면 `masking_status="succeeded"`, `has_masked_data=false`, `masked_types=[]`다. `has_masked_data=false`는 마스킹 미실행을 뜻하지 않는다.
- `masked_types`는 문장 안의 `[PERSON]`, `[PHONE_NUMBER]`, `[ACCOUNT_NUMBER]`, `[RRN]`, `[OTP]`, `[ADDRESS]`, `[CARD_NUMBER]`, `[BIRTH]`, `[EMAIL]`, `[PW]`, `[MASKED]`와 일치해야 한다. 원문 필드는 전송하지 않는다.
- `utterance_id`는 1부터 연속이며 한 세션은 요청 순서대로 처리한다. 앱은 앞선 분석 결과를 확인하고 다음 요청을 보낸다. 분석 실패·응답 유실 시 다음 번호를 보내지 않고 현재 세션의 후속 처리를 중단한다. 서버는 마스킹 성공 선언과 토큰 계약을 확인하지만 남은 개인정보를 직접 탐지하지 않는다.
- STT와 분석은 현재 ID로 연결하는 별도 API다. 서버는 이 ID가 실제 STT에서 발급됐는지까지 검사하지 않으며 앱 소유권 인증도 아직 없다.
- 전체 세션 문맥으로 OpenAI 보정·문맥 판단 한 번 호출 → 보정 문장+이전 최대 5개로 AI 분석 → 최근 20개 누적 계산·기존 경고 → 함께 저장 후 응답한다. `PIC_CONTEXT_MODEL` 미설정이면 LLM을 생략하고 마스킹 입력으로 AI를 실행한다.
- 보정 실패 시 검증된 `masked_text`를 사용한다. 응답·저장 기록의 `correction_status`는 성공 시 `ok`, 대체 입력 사용 시 `fallback`이다. 과거 기록이나 보정 없이 만든 결과는 null일 수 있다.

응답의 주요 필드:

| 필드 | 의미 |
|---|---|
| `conversation_id`, `utterance_id`, `revision`, `sequence` | 통화·발화·버전·순서 |
| `analysis_status` | AI 성공 `ok` / 실패 `error` |
| `correction_status` | 보정 `ok` / 마스킹 입력 대체 `fallback` |
| `current_text` | 실제 분석에 사용한 마스킹 텍스트 |
| `current_risk_score`, `cumulative_risk_score` | 현재·누적 점수, 0~100 |
| `type_scores`, `detected_types` | 유형별 0~100 점수·감지 유형 |
| `calculation` | 계산 설정·최근 창 발화 ID·계산 상세 |
| `warning`, `evidence` | 기존 경고 모듈의 상태·근거 |
| `context_judgment` | 별도 문맥 판단의 실행 상태·모델·설명·근거 ID |

전체 응답 스키마는 새 서버 `/docs`의 `CalculationPreviewResponse`에 공개한다. `PIC_AI_MODE=development`의 점수는 연결 확인용이며 성능 근거로 사용할 수 없다.

### 실패와 재시도

- 422: 마스킹 미성공·토큰 불일치·입력 형식 오류. 입력을 수정해야 한다.
- 409: 발화 중복·순서 충돌·이전 AI 실패 미복구·종료된 통화 등. 무조건 다음 번호로 진행하지 않는다.
- 503: AI 미설정 또는 경고·저장 실패. 실제 모델을 준비한 후 사용한다. 서버 기본 AI 모드는 disabled다.
- AI 실행 실패는 HTTP 200이어도 `analysis_status="error"`이고 현재·누적 점수, 유형 및 계산 필드는 null이다. 기존 마지막 성공 점수를 0점으로 덮어쓰지 않는다.
- 통합 LLM 실패 시 `correction_status="fallback"`, `context_judgment.status="error"`이며 검증된 마스킹 입력으로 AI를 실행한다. AI 성공이면 HTTP 200, `analysis_status="ok"`로 다음 발화를 처리할 수 있다. LLM 성공 후 AI만 실패하면 문맥 판단은 `ok`로 보존되며 AI 점수는 null이다.

AI 실패 기록은 다음 API로 복구한다. OpenAI를 다시 호출하지 않으며 같은 발화의 보정 문장·`correction_status`·`context_judgment`를 그대로 유지한다. 통합 LLM만 실패한 경우의 별도 재시도 API는 없다.

`POST /api/v1/utterances/analyze/retry`

```json
{"conversation_id":"ready에서 받은 ID","utterance_id":1}
```

통화의 마지막 실패 발화만 가능하며 성공 응답 후 다음 번호를 전송한다. 기록이 없으면 404다. 응답을 못 받았다고 발화 번호를 올리지 않는다. 먼저 7절의 결과 조회로 저장 여부를 확인한다.

## 6. 문맥 판단 응답

[문맥 판단 계약](CONTEXT_RISK_CONTRACT.md)에 입력 범위·판단 기준·서버 설정을 정리했다. 앱은 기존 분석 요청을 보내면 되며 응답에서 다음 객체를 읽는다.

```json
{
  "context_judgment": {
    "status": "ok",
    "model": "서버에서 설정한 모델 이름",
    "result": {
      "assessment": "suspicious",
      "reason": "기관 사칭 이후 이체 요구가 이어집니다.",
      "evidence_utterance_ids": [1, 2],
      "risk_types": ["institution_impersonation", "money_transfer"]
    }
  }
}
```

| status | 의미와 앱 처리 |
|---|---|
| `ok` | `result`의 문맥 설명·근거를 추가 안내로 사용 |
| `error` | 호출·응답 실패. `result=null`. 기존 AI 점수·경고를 유지하고 문맥 판단 불가로 구분 |
| `not_run` | 서버 통합 LLM 모델 미설정 또는 해당 필드가 없는 과거 기록. `result=null`, 모델 미설정이면 `model=null` |

`result.assessment`는 `suspicious`, `no_clear_risk`, `insufficient_context` 중 하나다. 근거 번호는 해당 통화의 마스킹된 발화를 참조한다. 과거 LLM 결과를 현재 성공 결과로 대신 표시하지 않는다.

앱은 기존 점수·경고를 유지하고 문맥 판단의 설명·근거를 추가 안내로 사용한다. `no_clear_risk`는 안전 보증이 아니며, 문맥 판단 실패를 위험도 0점으로 표시하지 않는다. LLM의 의심 판단만으로 기존 경고 알림 이벤트가 생성되는 것은 아니다. 문맥 응답 수신·표시까지의 Android 연결은 아직 미검증이다.

## 7. 저장 결과 조회

`GET /api/v1/utterances/results?conversation_id=세션ID`

- `utterance_id`를 생략하면 최신 결과, `&utterance_id=1`처럼 전달하면 해당 발화 결과다.
- 분석 API와 같은 `CalculationPreviewResponse`를 반환하며 `context_judgment`도 그대로 포함한다. AI·LLM을 다시 호출하지 않는다.
- 종료 후에도 조회할 수 있다. 조회 응답은 `Cache-Control: no-store`다.
- 통화 또는 해당 발화가 없으면 404, 잘못된 쿼리는 422, 저장소 오류는 503이다.
- 분석 응답을 잃었으면 해당 번호로 조회한다. 저장된 실패는 AI 재시도 API로 복구하고, 성공은 그대로 반영한다. 404가 곧 요청이 절대 처리되지 않았다는 보장은 아니므로 번호를 증가시키지 않는다. 같은 요청을 재전송해 중복 409를 받으면 다시 조회한다.

## 8. 경고 알림 조회·수신확인

`GET /api/v1/notifications?conversation_id=세션ID`

응답에는 `conversation_id`, `conversation_status`(`active`/`ended`), `notifications` 배열이 있다. 배열의 각 항목은 `event_id`, `conversation_id`, `created_at`, 발생 당시의 `warning`·`evidence`, `status`, `acknowledged_at`, `expired_at`을 포함한다. 조회는 `pending` 알림만 제공하며 종료된 통화는 빈 배열이다. 조회 응답은 `Cache-Control: no-store`다.

조회만으로 확인 처리하지 않는다. 앱은 `(conversation_id, event_id)`로 중복 표시를 막고 알림을 처리한 뒤 다음 요청을 보낸다. 이 API는 앱 화면용이며 푸시 알림 전송이 아니다.

`POST /api/v1/notifications/ack`

```json
{"conversation_id":"세션ID","event_id":"조회에서 받은 이벤트 ID"}
```

- 해당 알림 객체를 반환한다. 처음 확인하면 `status="acknowledged"`와 확인 시각을 저장한다.
- 반복 요청은 최초 확인 결과를 유지한다. 종료로 만료된 알림은 `status="expired"`로 반환하며 앱에서 다시 표시하지 않는다.
- 없는 통화·이벤트는 404, 잘못된 입력은 422, 저장소 오류는 503이다. 저장 실패 시 확인 완료로 처리하지 않는다.
- 별도 LLM 문맥 판단만으로 이 알림 이벤트를 생성하지 않는다.

## 9. 통화 종료 확정

앱의 정상 종료 순서:

```text
마이크 중단 → 마지막 음성 뒤 STT stop
 → 마지막 transcript와 stopped 수신
 → 받은 발화의 마스킹·분석을 순서대로 마무리
 → 마지막 분석 응답 확인 → HTTP 종료 → 최종 화면 표시
```

`POST /api/v1/conversations/end`

```json
{"conversation_id":"세션ID","last_utterance_id":3}
```

`last_utterance_id`는 STT `stopped.last_utterance_id`이며 1 이상의 정수다. 서버에 저장된 마지막 번호와 같아야 한다. STT 기록과의 대조는 아직 없으므로 앱이 실제 마지막 번호를 보내야 한다. 일반 종료는 마이크나 STT를 직접 끄지 않는다.

| 응답 필드 | 의미 |
|---|---|
| `conversation_id`, `conversation_status` | 해당 통화, `ended` |
| `ended_at` | 최초 종료 시각 |
| `warning`, `evidence` | 종료 시점의 경고 안내·근거 |
| `last_analysis` | 마지막 저장 분석 응답 전체. 점수·보정 상태·문맥 판단 포함 |

- 이미 잠금을 잡고 처리 중인 분석은 저장이 끝난 뒤 종료한다. 아직 도착하지 않은 발화는 기다릴 수 없으며 마지막 번호가 다르면 409를 반환하고 통화를 유지한다.
- 마지막 AI 분석이 실패했더라도 기록을 보존하고 종료할 수 있다. 이때 `last_analysis.analysis_status="error"`이므로 마지막 성공 결과와 분석 미완료를 표시한다. `ended`는 통화 처리 종료이며 모든 분석 성공을 뜻하지 않는다. 복구가 필요하면 종료 전에 재시도한다.
- 종료하면 활성 경고를 마무리하고 미확인 알림을 만료한다. 새 분석·AI 재시도는 409로 차단하고 저장 결과 조회는 유지한다.
- 같은 마지막 번호로 반복 종료하면 최초 종료 시각과 같은 결과를 반환한다. 최상위 경고는 종료 상태, `last_analysis.warning`은 분석 당시 상태이므로 구분해서 사용한다.
- 저장된 통화가 없으면 404, 필수 필드·형식 오류는 422, 마지막 번호 불일치는 409, 경고·저장 오류는 503이다. 503이면 종료 성공으로 표시하지 말고 같은 요청으로 재시도한다.
- 발화가 전혀 없어 `stopped.last_utterance_id=0`이면 저장할 분석 기록이 없다. 앱은 HTTP 종료를 호출하지 않고 STT 종료 후 '분석할 발화 없음'으로 끝낸다. 서버에 빈 통화 기록을 만들지 않는다.
- STT 오류나 마스킹 실패로 마지막 발화까지 처리하지 못했다면 전체 완료로 표시하지 않는다. 일반 종료는 기록 삭제나 동의 철회가 아니며 철회·삭제 API는 후속 작업이다.

## 10. 구현·검증 범위와 남은 확인

- 결과 조회·알림·종료 연결: `analysis/router.py`, `analysis/lifecycle_router.py`. 기존 서비스·파일 저장·통화 잠금을 재사용한다.
- 새 연결 테스트 4개와 기존 종료 호환성 1개, 총 5개 통과. 진행 중 분석 반영 후 종료, 반복 종료·수신확인, 알림 만료, 마지막 번호 불일치, 저장 실패 시 기록 보존을 확인했다. 외부 API·실제 모델은 이 테스트에서 호출하지 않았다.

- `stt/router.py`: 앱 순서 관리·중계·타임아웃·자원 정리.
- `stt/elevenlabs.py`: 접속·인증 헤더·Base64 변환·확정 요청·공급자 응답 검증.
- `stt/contracts.py`: 앱 메시지 타입과 경계 검증.
- 관련 테스트 14개 통과. 600초 제한은 테스트에서 1초로 줄여 같은 종료 경로를 확인했다.
- 외부 API·실제 음성·Android는 미검증이다. 특히 2초 미만의 짧은 입력, 무음 구간의 빈 확정 응답, 5초 분할 품질·지연은 실제 공급자에서 확인해야 한다. 확정 응답이 없으면 시간 초과 오류로 끝나며 성공으로 간주하지 않는다.
- 앱·자체 서버는 음성·원문을 파일이나 로그에 남기지 않는다. WebSocket 프레임·인증 헤더가 노출될 수 있는 디버그 로깅은 켜지 않는다. 공급자 측 보관 정책은 자체 서버의 미저장과 별개이며 실제 사용 전 고지 범위를 확인한다.
- 현재 경로에는 앱 사용자 인증·세션 복구가 없다. 외부 배포 전 접근 제한은 배포 단계에서 정한다.

참고: [ElevenLabs 이벤트](https://elevenlabs.io/docs/eleven-api/guides/how-to/speech-to-text/realtime/event-reference), [발화 확정 방식](https://elevenlabs.io/docs/eleven-api/guides/how-to/speech-to-text/realtime/transcripts-and-commit-strategies).

### Android 분석 연결 상태 (2026-11-06)

Android 작업 트리에 마스킹 성공 발화를 순서대로 전송하고 응답의 누적 점수·경고·문맥 설명을 표시하는 경로를 추가했다. 전송에는 `MaskedTranscript`만 사용한다. 서버 결과가 실패하거나 응답을 확인할 수 없으면 이후 발화 분석을 중단한다. AI 실패 복구·응답 유실 후 조회·서버 기록 삭제 연결은 아직 구현하지 않았다. 최신 앱은 받은 발화의 마스킹·분석을 마친 뒤 서버의 전체 통화 종료 API를 호출하며, 완료 응답을 확인하기 전에는 최종 완료로 표시하지 않는다. 발화가 없으면 종료 API를 호출하지 않는다. 종료 확인 실패 시 마지막 성공 결과를 유지하고 현재 화면에서 재시도할 수 있다. 앱을 떠나거나 종료한 후 재시도 상태를 보존하는 기능은 아직 없다.

2026-11-06 후속: 앱은 분석 실패 시 음성 수집을 중단하고 사용자가 재확인하면 발화별 조회를 수행한다. 성공 결과는 재사용하고, 저장된 AI 실패는 재시도 API로 복구한다. 조회 404일 때 같은 발화를 재전송하고 409라면 다시 조회하며, 복구 전 다음 발화 처리를 기다린다. 실기기 실패 복구 검증과 앱 종료 후 복구는 남았다. 위 단락 중 AI 실패 복구·응답 유실 조회 미구현이라는 설명은 이 후속 기록으로 대체한다.

2026-11-06 철회 API 기초: `POST /api/v1/conversations/withdraw`에 `{"conversation_id":"세션ID"}`를 보내면 철회 표시와 저장 기록 삭제 후 `{"conversation_id":"세션ID","status":"deleted"}`를 반환한다. 반복 요청은 성공한다. 삭제 실패는 503이며 철회된 세션의 이후 분석·조회는 409다. 단일 프로세스 기준이고 외부 제공자 데이터는 삭제하지 않는다. 아직 앱에서 호출하지 않으며, 인증·세션 소유권 확인이 없어 외부 공개 전에 보완해야 한다.

Android 후속 연결: 분석 요청 전에 서버 주소와 세션 ID를 앱의 동의 저장소에 등록하고, 철회 시 각 ID를 이 API에 전달한다. 삭제 응답을 확인한 ID만 제거하고 실패하면 재실행 후에도 대기 상태에서 재시도한다. 이 기능 이전에 생성되어 앱이 ID를 보관하지 않은 세션은 자동 삭제 대상에서 제외된다. 대체 서버 기준 단위 테스트·빌드는 통과했으며 실제 기기와 서버의 철회 전체 흐름은 확인 전이다. 위의 앱 미호출 문구는 이 후속 기록으로 대체한다.

사용자 요청에 따라 OTP 문맥 표현이 있는 발화와 이후 최대 두 발화에서 세 자리 이상의 숫자 또는 한글 숫자열을 `[OTP]`로 보호하는 규칙을 추가했다. 이 규칙은 모든 OTP 표현이나 STT 오인식을 탐지한다고 보장하지 않는다. NER·정규식 등 전체 마스킹 정확도와 변경 후 실제 앱-서버 종단 동작은 실기기에서 별도 확인한다.


### Android 일반 종료 연결 (2026-11-06)

실기기에서 사용자가 위험도 갱신과 마지막 발화 처리까지 확인한 후, 앱에 서버 종료 호출을 추가했다. 대체 서버 테스트에서 마지막 ID 전송, 종료 결과 표시, 실패 후 동일 요청 재시도, 발화 없는 종료를 확인했다. Android 단위 테스트 31개와 debug 빌드 성공; 실제 서버와 새 APK의 종료 API 종단 확인은 대기 중이다.
