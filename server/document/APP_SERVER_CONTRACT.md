# 앱 ↔ 새 서버 연결 계약

갱신: 2026-10-29. 대상은 `server.main:app`이며 기존 `backend.main:app`과 구분한다.

현재 구현 범위는 **STT WebSocket 중계와 마스킹 발화 분석·AI 재시도 HTTP API**다. 대체 객체로 확인했으며 실제 외부 API·모델·Android 연결은 검증하지 않았다. 사용자 요청으로 STT 실연결·앱 작업은 보류하고 서버 작업을 진행한다. 전체 세션 종료·철회·삭제 API는 새 서버에 아직 없다.

## 1. 연결 주소와 기본 규칙

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
- **STT 종료이지 전체 분석 완료가 아니다.** 앱은 이미 받은 발화의 마스킹·분석 응답까지 반영한 뒤 최종 화면을 확정한다. 전체 분석 종료 API는 이후 연결한다.

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
 → [이후 연결] 처리 중인 위험 분석까지 반영 → 전체 세션 종료
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
- `masked_types`는 문장 안의 `[PERSON]`, `[PHONE_NUMBER]`, `[ACCOUNT_NUMBER]`, `[RRN]`, `[OTP]`, `[ADDRESS]`와 일치해야 한다. 원문 필드는 전송하지 않는다.
- `utterance_id`는 1부터 연속이며 한 세션은 요청 순서대로 처리한다. 앱은 앞선 결과를 확인하고 다음 요청을 보낸다. 서버는 마스킹 성공 선언과 토큰 계약을 확인하지만 남은 개인정보를 직접 탐지하지 않는다.
- STT와 분석은 현재 ID로 연결하는 별도 API다. 서버는 이 ID가 실제 STT에서 발급됐는지까지 검사하지 않으며 앱 소유권 인증도 아직 없다.
- 보정 → 현재+이전 최대 5개 문맥 → AI → 최근 20개 누적 계산 → 경고·근거 → 저장 후 응답한다.
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

전체 응답 스키마는 새 서버 `/docs`의 `CalculationPreviewResponse`에 공개한다. 별도 LLM 문맥 판단 결과는 아직 포함하지 않는다. `PIC_AI_MODE=development`의 점수는 연결 확인용이며 성능 근거로 사용할 수 없다.

### 실패와 재시도

- 422: 마스킹 미성공·토큰 불일치·입력 형식 오류. 입력을 수정해야 한다.
- 409: 발화 중복·순서 충돌·이전 AI 실패 미복구·종료된 통화 등. 무조건 다음 번호로 진행하지 않는다.
- 503: AI 미설정 또는 경고·저장 실패. 실제 모델을 준비한 후 사용한다. 서버 기본 AI 모드는 disabled다.
- AI 실행 실패는 HTTP 200이어도 `analysis_status="error"`이고 현재·누적 점수, 유형 및 계산 필드는 null이다. 기존 마지막 성공 점수를 0점으로 덮어쓰지 않는다.

AI 실패 기록은 다음 API로 복구한다. 보정을 다시 호출하지 않으며 기존 `correction_status`를 유지한다.

`POST /api/v1/utterances/analyze/retry`

```json
{"conversation_id":"ready에서 받은 ID","utterance_id":1}
```

통화의 마지막 실패 발화만 가능하며 성공 응답 후 다음 번호를 전송한다. 기록이 없으면 404다. 응답을 못 받았다고 발화 번호를 올리지 않는다. 네트워크 실패 후 처리 여부 확인을 위한 결과 조회 API는 후속 작업으로 남아 있다.

## 6. 문맥 판단 응답 — 연결 예정

[문맥 판단 계약](CONTEXT_RISK_CONTRACT.md)에 별도 `context_judgment` 필드의 예정 형식을 정리했다. 현재는 내부 타입·응답 파서만 있으며 실제 분석 HTTP 응답에는 추가하지 않았다.

연결 후 앱은 기존 점수·경고를 유지하고 문맥 판단의 설명·근거를 추가 안내로 사용한다. `no_clear_risk`는 안전 보증이 아니며, 문맥 판단 실패를 위험도 0점으로 표시하지 않는다. LLM의 의심 판단만으로 기존 경고 알림 이벤트가 생성되는 것은 아니다.

## 7. 구현·검증 범위와 남은 확인

- `stt/router.py`: 앱 순서 관리·중계·타임아웃·자원 정리.
- `stt/elevenlabs.py`: 접속·인증 헤더·Base64 변환·확정 요청·공급자 응답 검증.
- `stt/contracts.py`: 앱 메시지 타입과 경계 검증.
- 관련 테스트 14개 통과. 600초 제한은 테스트에서 1초로 줄여 같은 종료 경로를 확인했다.
- 외부 API·실제 음성·Android는 미검증이다. 특히 2초 미만의 짧은 입력, 무음 구간의 빈 확정 응답, 5초 분할 품질·지연은 실제 공급자에서 확인해야 한다. 확정 응답이 없으면 시간 초과 오류로 끝나며 성공으로 간주하지 않는다.
- 앱·자체 서버는 음성·원문을 파일이나 로그에 남기지 않는다. WebSocket 프레임·인증 헤더가 노출될 수 있는 디버그 로깅은 켜지 않는다. 공급자 측 보관 정책은 자체 서버의 미저장과 별개이며 실제 사용 전 고지 범위를 확인한다.
- 현재 경로에는 앱 사용자 인증·세션 복구가 없다. 외부 배포 전 접근 제한은 배포 단계에서 정한다.

참고: [ElevenLabs 이벤트](https://elevenlabs.io/docs/eleven-api/guides/how-to/speech-to-text/realtime/event-reference), [발화 확정 방식](https://elevenlabs.io/docs/eleven-api/guides/how-to/speech-to-text/realtime/transcripts-and-commit-strategies).
