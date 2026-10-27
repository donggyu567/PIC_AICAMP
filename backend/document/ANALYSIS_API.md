# 계산·저장·재시도·통화 종료·알림 API

이 문서는 AI 결과를 직접 입력하는 개발용 API와 통합 분석이 공유하는 저장 규칙을 설명한다. 서버 실행은 [시작 안내](README.md), 앱 발화 입력은 [통합 분석](INTEGRATED_ANALYSIS_API.md)을 참고한다.

## 샘플 결과로 계산 확인

AI를 비활성화해 실행한 뒤 Swagger의 `POST /api/v1/dev/model-results`에서 기본 Example Value를 사용한다. 이 경로는 LLM·AI를 호출하지 않는다. 정상 서버 시작 시에는 실제 경고 모듈을 사용한다.

1. 새로운 통화 ID로 기본 샘플을 실행한다. 현재 점수 55, 누적 점수 약 55가 반환된다.
2. 같은 통화의 `utterance_id`와 `sequence`를 2로 바꾸고 전송한다. 두 번째 누적 점수는 약 73.75다.
3. 같은 요청을 다시 보내면 중복으로 409가 반환된다.

입력 형식은 `ModelResultRequest`이며 `conversation_id`, `utterance_id`, `revision`, `sequence`, `tuned_text`, `analysis_status`, `is_phishing_score`, `type_scores`, `detected_types`, `model_version`을 받는다. 신규·재시도 모두 현재 `revision=1`만 지원한다.

성공이면 현재 점수와 8개 유형별 점수를 모두 제공한다. 감지 유형이 없으면 `detected_types=[]`다. 실패이면 `analysis_status="error"`로 두고 `is_phishing_score`, `type_scores`, `detected_types`를 모두 `null`로 전달한다.

유형은 `institution_impersonation`, `money_transfer`, `personal_information`, `app_installation`, `secrecy`, `threat_pressure`, `loan_fraud`, `information_probing`이다. 추가·누락 유형, 중복 감지 유형, 범위 밖 점수는 허용하지 않는다.

## 누적 계산

AI 입력 점수는 0~1이고, 응답 점수는 0~100이다. 반올림은 하지 않는다. 현재 개발 기본 설정은 `window_size=20`, `rho=0.95`, `b=0.1`, `policy_version="risk-policy-v1"`이다. 검증 완료된 운영 임계값은 아니다.

현재 발화의 순서를 `t`, 계산 창의 각 발화 점수를 `p_i`로 두면 다음과 같다.

```text
유효 위험값 d_i = max(0, (p_i - b) / (1 - b))
시간 가중치 w_i = rho ** (t - i)
발화 기여값     = w_i × d_i
창 최대값 M    = max(p_i)
누적값 A       = 1 - product(1 - w_i × d_i)
최종 누적 점수 = 100 × max(M, A)
```

매번 현재 발화를 포함한 최근 창으로 다시 계산한다. 이전 누적 점수에 새 점수를 더하지 않는다. 통화 초기에는 현재까지 존재하는 발화를 사용한다. 분석 실패는 0점으로 바꾸거나 계산에서 조용히 제외하지 않고, 복구 전 후속 발화를 차단한다.

설정은 첫 결과와 함께 통화 파일에 저장한다. 기본값을 바꾸어도 이미 생성된 통화에는 저장된 설정을 계속 적용한다.

## 반환 형식

`CalculationPreviewResponse`의 주요 필드는 다음과 같다.

| 필드 | 의미 |
|---|---|
| `conversation_id`, `utterance_id`, `revision`, `sequence` | 통화·발화 식별 정보 |
| `analysis_status`, `current_text` | 분석 상태와 분석에 사용한 보정 문장 |
| `current_risk_score`, `cumulative_risk_score` | 현재·누적 점수, 0~100 |
| `type_scores`, `detected_types` | 현재 발화의 유형별 점수와 감지 유형 |
| `calculation` | 창 최대 점수, 누적식 점수, 창 발화 ID와 실제 계산 설정 |
| `warning`, `evidence` | 경고 모듈의 상태·문구와 통화 전체 근거 |

유효한 분석 실패도 HTTP 200으로 반환한다. 이때 현재·누적 점수, 유형, `calculation`은 `null`이다. 경고 모듈은 이전 경고·근거를 유지하고 실패 안내를 반환한다. 경고 미연결 상태의 `warning=null`은 안전 판정을 의미하지 않는다.

## 저장과 복원

저장 위치는 프로젝트의 `backend/data/analysis/<통화 ID SHA-256>.json`이다. 실행 위치와 무관하게 같은 경로를 사용하고, 저장 시 폴더를 생성한다.

| 저장 필드 | 내용 |
|---|---|
| `storage_version`, `conversation_id` | 파일 형식 버전과 통화 ID |
| `conversation_status`, `ended_at` | 진행·종료 상태와 UTC 종료 시각 |
| `policy` | 통화별 계산 설정 |
| `records` | 발생 순서별 `model_result`, `response`, `previous_attempts` |
| `warning_config`, `warning_state` | 통화별 경고 설정·마지막 상태 |
| `final_warning_result` | 통화 종료 시 별도로 보존한 최종 안내·근거 |
| `notifications` | 발생 당시 경고·근거와 알림 처리 상태·시각 |
| `pending_notification_ids` | `notifications`의 `pending` ID와 일치하는 호환용 목록 |

`response`가 앱에 반환하는 JSON이다. 저장 파일 전체는 서버 복원용 형식이며 외부 응답과 다르다.

처리는 통화 잠금 → 파일 읽기·검증 → 신규 또는 재시도 조건 확인 → 계산·경고·응답 생성 → 파일 저장 → 반환 순서다. 전체 기록의 순서·중복 검증은 한 번 순회하며, 계산용 공통 객체는 필요한 최근 창만 구성한다. 전체 기록 자체는 조회·근거·실패 이력을 위해 보존한다.

임시 파일에 UTF-8 JSON을 쓰고 `flush`/`fsync`한 뒤 같은 폴더에서 `os.replace`로 교체한다. 교체 전 오류가 발생하면 기존 파일을 유지한다. 손상된 파일을 빈 통화로 간주해 덮어쓰지 않는다.

서버 재시작 후에도 같은 파일에서 계산·문맥·경고·알림 처리 상태를 복원한다. 같은 통화의 읽기·계산·쓰기·종료·수신확인은 같은 프로세스의 통화별 잠금으로 보호한다. **단일 worker 전용이며 프로세스 간 잠금은 없다.** 전체 파일을 매번 읽고 교체하는 비용은 남아 있다.

이전 파일의 알림 ID 목록은 읽을 때 최초 경고 이벤트의 저장 응답과 연결해 `notifications`로 복원한다. 생성 시각은 추측하지 않고 `null`로 두며, 종료된 통화의 알림은 기존 종료 시각에 만료된 것으로 복원한다. 조회만으로 파일을 다시 저장하거나 과거 발화 응답을 수정하지 않는다.

## 저장 결과 조회

`GET /api/v1/dev/model-results`의 `conversation_id`는 필수이고, `utterance_id`는 선택이다.

```text
/api/v1/dev/model-results?conversation_id=api-test-001
/api/v1/dev/model-results?conversation_id=api-test-001&utterance_id=1
```

발화 ID를 생략하면 최신 응답을 반환한다. 조회는 AI·경고 호출이나 재계산 없이 저장 응답을 반환한다. 통화·발화가 없으면 404다. 실패 복구 후에는 복구된 현재 응답을 반환하고, 이전 실패는 파일의 `previous_attempts`에 남는다.

POST 응답을 받지 못해 같은 발화를 재전송했는데 409가 나오면, 해당 발화 ID로 조회하여 이미 저장되었는지 확인한다.

## 마지막 실패 발화 재시도

`POST /api/v1/dev/model-results/retry`는 AI를 호출하지 않고 재분석 결과를 받는다. 요청 형식은 신규 결과 등록과 같다.

- 통화의 마지막 발화가 현재 실패 상태여야 한다.
- `conversation_id`, `utterance_id`, `sequence`, `revision`, `tuned_text`가 저장된 실패 기록과 같아야 한다.
- `model_version`은 재분석에 실제 사용한 버전을 받는다.
- 이전 실패 입력·응답을 `previous_attempts`에 추가하고 현재 결과를 교체한다. 발화 수·순서는 늘어나지 않는다.
- 재실패도 저장할 수 있으며 후속 발화 차단을 유지한다. 성공한 뒤에는 다음 발화를 다시 전송할 수 있다.

서버가 차단된 후속 요청을 대기열에 보관하지는 않는다. 성공한 발화의 문장 수정과 후속 재분석은 아직 지원하지 않는다. 재시도 저장이 실패하면 기존 실패 기록과 이력을 유지한다.

확인 순서는 1번 성공 → 2번 실패 → 3번 요청 409 → 2번 재시도 성공 → 3번 재전송이다. 통합 분석의 AI 재호출 경로는 [통합 분석 문서](INTEGRATED_ANALYSIS_API.md)를 참고한다.

## 통화 종료

`POST /api/v1/conversations/end` 요청:

```json
{"conversation_id": "api-test-001"}
```

종료 상태를 저장하고 `conversation_id`, `conversation_status="ended"`, UTC `ended_at`, 최종 `warning`·`evidence`를 반환한다. 경고를 사용하지 않은 통화의 두 경고 필드는 `null`이다.

- 반복 종료는 경고 호출·저장 없이 최초 종료 시각과 최종 결과를 그대로 반환한다. 저장된 통화가 없으면 404다.
- 실패 기록이 있어도 종료할 수 있으나, 이후 신규 분석과 실패 재시도는 409로 차단한다.
- AI·LLM은 호출하지 않고 경고 모듈에 `conversation_ended=True`를 전달한다. 활성 경고 이벤트를 닫고 종료 안내·근거를 `final_warning_result`에 보존한다.
- 기존 GET 조회는 가능하며 과거 분석 응답·실패 이력·위험 점수·근거는 그대로 유지한다. 과거 응답의 경고 상태는 분석 당시의 상태다.
- 미확인 알림은 `expired`로 바꾸고 `expired_at`에 통화 종료 시각을 기록한다. 이미 확인한 알림은 바꾸지 않는다.
- 통화 종료·최종 경고·알림 만료를 한 파일로 저장한다. 경고 호출 또는 저장이 실패하면 503이며 기존 기록은 유지한다.
- 분석이 먼저 통화 잠금을 얻으면 분석 저장 후 종료하고, 종료가 먼저면 이후 분석을 차단한다.

이전 버전에서 통화 상태만 종료한 경고 통화는 종료 API를 처음 다시 호출할 때 경고 종료를 보완한다. 기존 `ended_at`은 유지한다. 경고 종료가 필요한 통화에 모듈이 없으면 503이며, 최종 결과가 이미 저장된 반복 종료에는 모듈이 필요하지 않다.

## 알림 조회·수신확인

새 경고 이벤트가 생기면 분석 결과와 알림 내용을 같은 파일에 저장한다. 동일 이벤트가 유지되는 동안 알림을 반복 생성하지 않는다. 이번 API는 통화 중 앱 화면 경고용 조회 방식이며, 앱의 조회·표시 연결과 푸시 전송은 별도 작업이다.

`GET /api/v1/notifications?conversation_id=api-test-001`은 다음 필드를 반환한다.

| 필드 | 의미 |
|---|---|
| `conversation_id` | 조회한 통화 ID |
| `conversation_status` | `active` 또는 `ended` |
| `notifications` | 해당 통화의 `pending` 알림 목록. 종료 통화는 빈 목록 |

조회만으로 알림을 확인 처리하지 않는다. 응답에는 `Cache-Control: no-store`를 지정하며, 확인 전 다시 조회하면 같은 이벤트 ID가 나온다.

각 알림의 형식은 다음과 같다.

| 필드 | 의미 |
|---|---|
| `event_id`, `conversation_id` | 알림 이벤트·통화 식별자 |
| `created_at` | UTC 생성 시각. 이전 ID 전용 파일에서 복원한 알림은 `null` |
| `warning`, `evidence` | 최초 발생 당시 문구·근거. 이후 경고가 갱신돼도 유지 |
| `status` | `pending`, `acknowledged`, `expired` |
| `acknowledged_at`, `expired_at` | 처리 상태에 해당하는 UTC 시각, 해당하지 않으면 `null` |

앱이 알림을 받아 처리한 뒤 `POST /api/v1/notifications/ack`를 요청한다. 이벤트 ID는 조회에서 받은 실제 값을 넣는다.

```json
{
  "conversation_id": "api-test-001",
  "event_id": "조회에서 받은 이벤트 ID"
}
```

응답은 해당 알림 기록 한 개다. `pending`이면 최초 확인 시각과 `acknowledged` 상태를 저장한 뒤 반환한다. 이미 확인한 알림은 최초 시각을 유지하고 재저장하지 않는다. 종료로 만료된 알림의 늦은 확인은 `expired` 상태 그대로 반환한다. 확인·만료 이력은 삭제하지 않는다.

알림 처리 후 확인 요청이 유실될 수 있으므로 앱은 `(conversation_id, event_id)`를 영속적으로 기록해 중복 표시를 방지해야 한다. 서버는 확인 전 재조회와 확인 요청 재전송을 지원하며, 화면 표시를 정확히 한 번만 수행하는 것까지 서버 단독으로 보장하지 않는다. 통화 종료 전에 시작한 조회 응답이 늦게 도착하면 앱도 해당 통화의 경고 표시를 차단해야 한다.

## 오류와 검증

| HTTP | 상황 |
|---|---|
| 200 + `analysis_status="error"` | 유효한 AI 실패 결과 저장 |
| 404 | 조회·재시도·종료할 통화·발화 또는 해당 통화의 알림 없음 |
| 409 | 중복·순서 오류, 이전 실패, 종료된 통화 또는 재시도 대상 불일치 |
| 422 | 입력 계약·점수·식별자 오류 |
| 503 | 파일 읽기·쓰기·형식 오류 또는 경고 연결 오류 |

외부 AI 없이 계산·저장·복구·종료를 검사하는 명령:

```powershell
.\.venv-ai\Scripts\python.exe -B -m unittest discover -s tests -p "*analysis_api.py" -v
.\.venv-ai\Scripts\python.exe -B -m unittest tests.test_notification_api tests.test_lifecycle_analysis_api -v
```

이 테스트들은 임시 저장 폴더와 대체 제공자 또는 실제 경고 구현체를 사용한다. 통화 분리, 최근 20개 제한, 정책 유지, 중복·순서, 실패 복구, 저장 실패·손상 파일 보호, 종료와 동시 요청 등을 검사한다. 알림 검증에는 반복 조회·수신확인, 종료 시 만료, 저장 복원과 이전 파일 호환을 포함한다. 경고 구현체 검증의 구분은 [경고 연동](WARNING_INTEGRATION.md)을 참고한다.
