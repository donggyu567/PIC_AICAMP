# 경고 모듈 서버 연결

서버 시작 시 `backend/lifespan.py`의 `lifespan()`이 실제 `DefaultWarningManager`를 `app.state.warning_manager`에 등록한다. AI를 비활성화해도 경고 모듈은 사용할 수 있다. 정책 판단·근거 관리·문구 생성은 `models/warning_manager`가, 계산·순서·저장·응답 조립은 서버가 담당한다.

## 통화별 설정

`prepare_warning_session()`은 요청 초기에 통화의 경고 연결 여부와 설정을 확인한다. 준비한 설정을 계산·경고 단계로 전달한다.

- 경고 연결 상태에서 시작한 통화는 매 발화마다 경고 모듈을 호출한다.
- 경고 없이 시작한 통화에 중간부터 모듈을 붙이면 409다. 현재는 새 통화 ID로 시작해야 한다.
- 경고를 관리하던 통화에서 모듈이 빠지면 503이다.
- 의도적으로 경고 구현체를 연결하지 않은 경로에서는 `warning`, `evidence`가 모두 `null`이다. 정상 서버 시작은 실제 구현체를 등록하므로 이 경우와 구분한다.

초기 설정은 `WarningConfig()`의 개별 근거 50점, 경고 70점, 대표 근거 수 3개, 정책 버전 `warning-v1`이다. 첫 처리에서 저장하고 재시도까지 같은 설정을 사용한다. 성능 검증이 끝난 운영 기준은 아니다.

## 호출과 저장 흐름

```text
통화의 경고 설정 준비
 → AI 결과 검증·누적 계산
 → 직전 경고 상태와 함께 update_warning() 호출
 → 반환 계약 검증
 → 점수 + warning + evidence 응답 조립
 → 분석 기록·응답·경고 상태·새 알림 내용을 함께 저장
```

경고 모듈 입력:

| 입력 | 내용 |
|---|---|
| `model_result` | 현재 분석 결과, AI 점수는 0~1 |
| `calculation_result` | 표시 단위 0~100 계산 결과, AI 실패 시 `None` |
| `previous_state` | 직전 저장 상태, 최초에는 `None` |
| `config` | 통화에 고정된 경고 설정 |
| `is_replay`, `conversation_ended` | 발화·재시도에서는 둘 다 `False`, 통화 종료에서는 `conversation_ended=True` |

실패 발화 재시도는 아직 성공하지 않은 마지막 발화를 처리하므로 실시간 호출이다. 문장 정정에 따른 과거 이력 재생은 아직 없다. 통화 종료는 아래의 별도 종료 흐름으로 처리한다.

경고 모듈 반환값:

| 반환 | 서버 처리 |
|---|---|
| `result.warning` | 상태·사유·안내 문구를 API 응답에 포함 |
| `result.evidence` | 최근·최고 위험 발화와 누적 경고 근거를 응답에 포함 |
| `state` | `warning_state`에 저장하여 다음 호출에 전달 |
| `notify_event_id` | 새 ID라면 발생 당시 `warning`·`evidence`를 알림 기록으로 만들고 분석 결과와 함께 저장 |

`warning_config`, `warning_state`, `pending_notification_ids`는 서버 내부 저장 필드다. `notifications`의 미확인 알림은 별도 조회 API로 제공한다. AI 문맥·계산 창과 달리 경고 근거는 통화 전체를 기준으로 보존한다.

## 통화 종료와 최종 결과

```text
POST /api/v1/conversations/end
 → 통화 잠금·기존 상태 조회
 → update_warning(..., conversation_ended=True)
 → 활성 경고 이벤트 종료·종료 안내 생성
 → 미확인 알림 만료
 → 종료 상태·최종 경고 결과·알림 상태를 함께 저장
 → 최초 종료 시각과 최종 warning·evidence 반환
```

`DefaultWarningManager`의 종료 분기는 기존 경고 상태를 `close_conversation()`으로 마무리한다. 활성 이벤트의 `closed_sequence`를 마지막 발화 순서로 기록하고 `active`를 `previous_warning`으로 바꾼다. 기존 점수·개별 근거·경고 이력은 보존하며 새 이벤트나 알림은 만들지 않는다. AI·LLM을 다시 호출하지 않으며 마지막 발화가 분석 실패여도 종료할 수 있다.

서버는 종료 안내·근거를 `final_warning_result`에 저장한다. 과거 발화의 `records[].response`를 바꾸지 않으므로, 발화 조회는 당시 응답을, 종료 API는 통화 종료 결과를 반환한다. 완료된 종료 요청을 반복하면 경고 호출·저장 없이 같은 종료 시각과 결과를 반환한다. 경고 없이 시작한 통화의 종료 결과에는 `warning`·`evidence`가 `null`이다.

이전 버전에서 종료 상태만 저장한 경고 통화는 처음 종료 API를 다시 호출할 때 경고를 마무리한다. 원래 `ended_at`은 유지한다. 미완료 종료에는 경고 모듈 연결이 필요하며, 이미 최종 결과가 저장된 종료는 모듈 없이도 재조회할 수 있다.

## 앱 화면용 알림 조회·수신확인

`backend/services/notification_service.py`는 `create_notification()`, `expire_notifications()`, `NotificationService.list_pending()`, `acknowledge()`로 알림을 관리한다.

- `GET /api/v1/notifications?conversation_id=...`: `pending` 알림을 반환한다. 조회는 확인 처리가 아니며 응답에 `Cache-Control: no-store`를 지정한다.
- `POST /api/v1/notifications/ack`: 통화·이벤트 ID로 수신확인한다. 최초 확인 시각을 저장하고, 반복 요청에도 같은 확인 결과를 반환한다.
- 통화 종료 시 미확인 알림은 `expired`가 된다. 종료 통화의 조회 목록은 비어 있고, 늦게 도착한 수신확인도 만료 상태를 바꾸지 않는다.

각 알림은 이벤트 ID, 통화 ID, 발생 당시 문구·근거, 생성 시각과 `pending`·`acknowledged`·`expired` 상태를 보존한다. `pending_notification_ids`는 `pending` 기록과 일치하는 호환용 필드다. 이전 파일의 ID만 있는 알림은 최초 경고 발화의 저장 응답으로 복원하며, 알 수 없는 발생 시각은 `created_at=null`로 둔다. 조회만으로 파일이나 과거 발화 응답을 다시 쓰지는 않는다.

앱은 `(conversation_id, event_id)`를 영속적으로 기록해 중복 표시를 막고 처리한 알림을 수신확인해야 한다. 확인 요청이나 응답이 유실되면 같은 ID로 다시 확인할 수 있다. 통화 종료 전에 요청한 조회 응답이 뒤늦게 도착할 수도 있으므로 앱도 종료된 통화의 실시간 경고 표시를 차단해야 한다. 서버 API 구현 범위이며 앱 연동·FCM 등 푸시 전송은 포함하지 않는다.

## 검증과 실패 처리

`backend/services/warning_service.py`의 `update_warning()`이 중첩 타입, 통화·설정, 응답·상태의 일치, 점수 단위, 알림 이벤트 존재 여부 등을 검사한다. 서버에서 정책 임계값으로 경고를 다시 판단하지 않는다. 입력·이전 상태는 복사해서 전달하여 경고 구현체가 수정해도 원래 기록을 보호한다.

AI 실패 시 현재·누적 점수와 현재 유형은 `null`이다. 경고 모듈에는 계산 결과 `None`을 넘기고, 이전 상태·근거를 유지한 실패 안내를 받는다. 첫 분석부터 실패했다면 상태는 `None`이다. 실패로 새 알림을 발생시킬 수 없다.

경고 모듈 예외나 잘못된 반환은 503이다. 해당 발화의 점수·경고 상태를 부분 저장하지 않는다. 종료 처리도 반환 검증과 파일 저장을 마친 뒤에만 성공으로 응답한다. 저장 파일 교체 실패 시 기존 기록을 유지하므로 종료 상태나 알림 확인 상태만 부분 반영하지 않는다. 통합 경로의 신규 요청을 다시 보내면 보정·AI가 재호출될 수 있다.

## 적용 경로와 테스트

경고 처리는 통합 분석·AI 재시도와 개발용 결과 입력·재시도에 연결된다. GET 조회는 저장된 경고·근거를 그대로 반환하며 모듈을 다시 호출하지 않는다.

```powershell
.\.venv-ai\Scripts\python.exe -B -m unittest discover -s tests -p "test_warning_analysis_api.py" -v
.\.venv-ai\Scripts\python.exe -B -m unittest discover -s tests -p "test_real_warning_api.py" -v
.\.venv-ai\Scripts\python.exe -B -m unittest tests.test_notification_api tests.test_lifecycle_analysis_api -v
```

첫 테스트는 대체 경고 구현체로 잘못된 반환, 상태 보존, 저장 실패 등 서버 계약을 검사한다. 두 번째는 실제 `DefaultWarningManager`의 시작 등록, 55점 발화 두 개의 누적 경고, 저장·조회와 실패 시 근거 보존을 검사한다. 마지막 명령은 종료·알림의 저장, 반복 요청, 실패·복원 흐름을 검사한다. 학습 모델의 탐지 정확도나 실제 앱 표시 검증은 포함하지 않는다.
