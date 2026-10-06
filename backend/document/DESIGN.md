# 발화 처리 API 서버 설계안

작성일: 2026-09-24. AI 구현 요약·상세 설계서 대조 및 사용자 선택 반영.
설계 단계이며 실행 코드, DB, 모델 파일은 생성·변경하지 않았다.

## 1. 확정한 방향과 근거

사용자 선택: **현재 발화 모델 + 최근 20개 발화 점수 누적**을 적용한다.
상세 설계서의 별도 ‘계산식/JSON 출력 초안’ 탭에 있는 통화 점수 학습 모델은 이번 범위에서 제외한다.

- 현재 발화 모델: KoELECTRA 공통 인코더 + 위험 여부 Head 1개 + 위험 유형 Head 8개.
- 모델 입력: current.tuned_text + 같은 통화의 이전 최대 5개 history[].tuned_text.
- 모델 판단 대상: 현재 발화. 과거 위험 유형을 현재 발화 유형으로 복사하지 않는다.
- 앱 표시 점수: 0~100점. 실제 보이스피싱 확률이라는 표현은 사용하지 않는다.
- 누적 범위: 현재 + 직전 19개 확정 발화의 점수.
- 경고와 근거: 통화 단위로 보존하며 최근 20개에서 빠졌다는 이유로 삭제하지 않는다.

제공된 구현 요약에는 tokenizer, forward, 합성 학습 단계, inference 경로를 확인했다고 기록되어 있다. 실제 전체 학습과 독립 성능 평가는 아직 진행하지 않았다고 명시되어 있다. 이번 작업에서는 AI 소스나 체크포인트를 직접 실행·검증하지 않았다.

초기 배포 형태는 소수 단말용 FastAPI 단일 프로세스와 발화별 REST 요청/응답으로 제안한다. DB는 SQLite를 제안하며, 실제 AI 실행 장비·패키지 경로·체크포인트는 인수 시 정한다.

## 2. 전체 흐름과 책임

```text
Android
  음성 → STT 확정 → 로컬 개인정보 마스킹
  → 로컬 저장 + 영속 전송 대기열
  → HTTPS 발화 전송
                 ↓
FastAPI / UtteranceService
  인증·소유권·입력 검증
  → 중복·순서 확인 및 요청 기록
  → llm_correction: 단일 발화 보정
  → context_manager: current + 이전 최대 5개
  → UtteranceRiskAnalyzer: 현재 점수 1개 + 유형 점수 8개
  → ConversationRiskPolicy: 최근 20개 점수 누적
  → WarningPolicy: 경고·근거 갱신
  → 결과 + 통화 상태를 함께 저장
  → JSON 응답
                 ↓
Android
  발화 ID·정정 버전·통화 상태 버전 확인 → 결과 화면 갱신
```

| 구성 요소 | 책임 | 관리하지 않는 것 |
|---|---|---|
| API | 인증, 소유권, HTTP 계약, 오류 변환 | 모델 내부 계산 |
| UtteranceService | 순서, 중복, 단계 진행, 재시도, 저장 조율 | 위험 점수 임의 생성 |
| llm_correction | 마스킹 토큰·의미를 보존한 보정 | 통화 누적 점수 |
| context_manager | 현재 발화와 이전 최대 5개 구성 | 경고·20개 점수 버퍼 |
| UtteranceRiskAnalyzer | tokenizer 및 학습된 발화 모델 실행 | 영속 통화 상태 |
| ConversationRiskPolicy | 저장된 발화 점수로 최근 누적 계산 | 텍스트 20개 재추론 |
| WarningPolicy | 이벤트·근거·경고 상태 변경안 계산 | DB 직접 쓰기 |
| Repository | 버전별 입력·결과·이벤트·통화 상태 저장 | 모델 호출 |

누적·경고 계산 코드는 AI 패키지에서 제공해도 된다. 다만 실제 통화 상태와 저장 책임은 서버 Repository에 모은다. AI 모듈과 backend에 각각 별도 통화 저장소를 만들지 않는다.

모듈 연결은 Python 객체를 기본으로 한다. 파일 저장 후 재읽기를 호출 규약으로 사용하지 않는다. 별도 AI 서버가 필요해지면 추론 어댑터만 HTTP 방식으로 교체한다.

## 3. 반드시 분리할 세 가지 이력

| 종류 | 범위 | 목적 |
|---|---|---|
| 모델 문맥 | current 1개 + 이전 최대 5개 | 현재 발화 의미 해석 |
| 점수 누적 창 | 현재 포함 최근 20개 확정 발화 | 최근 위험 신호 계산 |
| 통화 경고·근거 | 통화 전체의 유효한 기록 | 과거 위험 발화와 경고 보존 |

최근 20개는 ‘분석 성공한 최근 20개’로 바꾸지 않는다. 실패한 발화를 0점으로 넣거나 제외하고 다음 점수를 정상 계산하지 않는다. 오류 해결 전에는 마지막 유효 통화 상태와 그 계산 시점을 표시한다.

현재 context_manager의 최대 6개 버퍼만으로 20개 누적·통화 전체 근거를 구현할 수 없다. 추가 저장 구조가 필요하다.

## 4. AI 입력·출력 계약

### 4.1 입력

기존 ConversationContext를 어댑터가 받아 모델에는 tuned_text만 전달한다.
masked_text, is_tuned, has_unclear, 식별자 등은 서버의 검증·복구 메타데이터로 보관하며 모델 입력 문장에 섞지 않는다.

```text
[CLS] history [SEP] current [SEP]
```

- history는 오래된 발화부터 정렬한다.
- 특수 토큰을 포함해 512토큰을 초과하면 가장 오래된 history 발화부터 제거한다.
- history를 모두 제거해도 current가 길면 INPUT_TOO_LONG으로 처리한다.
- current를 임의로 자르거나 여러 발화로 분할하지 않는다.
- 해당 모델 tokenizer로 길이를 판단하며 문자 수로 대체하지 않는다.
- 학습·추론 전처리를 맞추고 right padding 및 sentence-pair 구분을 유지한다.
- 실제 사용된 history의 발화 ID·revision과 tokenizer/전처리 버전을 기록한다.

현재 서버의 10,000자 입력 제한과 모델의 512토큰 제한은 서로 다르다. HTTP 검증을 통과해도 보정 결과가 모델 입력 한도를 넘을 수 있다.

### 4.2 발화 추론 결과

모델 본체는 raw logits를 반환하고 추론 계층에서 sigmoid를 한 번 적용한다.
서버 어댑터의 표준 내부 계약은 다음으로 제안한다.

```text
UtteranceScores
  risk_probability: float                 # 0~1 모델 신호, 보정된 실제 확률 아님
  type_probabilities: dict[label, float]   # 8개 전체, 각각 0~1
  model_version
  tokenizer_version
  preprocessing_version
  used_history: [(utterance_id, revision), ...]
```

실제 AI 패키지가 이미 0~100점으로 반환한다면 어댑터에서 내부 단위로 한 번만 변환한다. sigmoid 또는 100배 변환을 중복 적용하지 않는다. 필드명 risk_probability는 내부 신호 명칭일 뿐이며 외부에는 score로 노출한다.

유형 순서는 아래와 같이 고정하고 모델의 label2id/id2label과 일치하는지 로딩 시 검증한다.

1. institution_impersonation
2. money_transfer
3. personal_information
4. app_installation
5. secrecy
6. threat_pressure
7. loan_fraud
8. information_probing

각 점수는 유한한 0~1 값이어야 하고 유형은 정확히 8개여야 한다. 유형별 임계값은 별도 설정으로 관리한다. 초기 제안값은 각각 0.5다.

두 Head는 독립적이므로 전체 위험 점수가 낮더라도 일부 유형 점수가 높을 수 있고, 위험 점수가 높아도 detected_types가 비어 있을 수 있다. 서버가 임의로 유형을 지우거나 보충하지 않는다. 학습 라벨 규칙을 추론 결과의 강제 변환 규칙으로 사용하지 않는다.

### 4.3 누적·경고 정책

상세 설계서 5장의 최근 20개 계산을 정책으로 구현한다.

- 낮은 점수 누적 제외 기준 b, 순서 가중치 rho를 적용한다.
- 현재 창의 점수들로 누적값을 매번 다시 계산한다. 직전 누적 점수에 다시 더하지 않는다.
- 최근 창의 최대 발화 점수와 약한 신호의 누적값 중 큰 값을 최종 누적 점수로 사용한다.
- 유형 점수는 누적식에 추가 가산하지 않는다.
- 통화 전체 최고 근거 점수를 현재 누적 점수의 하한으로 넣지 않는다.
- 초기 설정: 창 20개, rho=0.95, b=0.10, 근거 저장 50점, 경고 70점. 창 20개는 사용자 선택이며 나머지 수치는 검증 전 제안값이다.
- 계산과 임계값 비교는 반올림 전 값으로 수행한다.
- 정책 버전에는 누적 설정·8개 유형 임계값·경고/근거 기준을 함께 기록한다.

Google Docs의 일부 수식 객체는 커넥터에서 본문 문자열로 추출되지 않았다. 수식 구현 때에는 원본 수식 또는 AI 담당자의 정책 코드를 대조하고, 아래 문서의 수치 예시로 검증해야 한다. 이번 설계에서는 읽히지 않은 수식을 원문 그대로 전사했다고 간주하지 않는다.

문서의 검증 예시: 25점 5회는 약 55.9점, 25점 10회는 약 76.3점, 55점 2회는 73.75점. 92점 뒤에 5점 19회면 누적 92점이고, 5점이 한 번 더 오면 최근 누적은 5점으로 내려가도 과거 경고·근거는 남는다.

경고 상태:
- none: 경고 이력 없음.
- active: 현재 최근 누적이 경고 기준 충족.
- previous_warning: 현재 기준 미만이나 유효한 과거 경고 있음.

경고 사유는 single_utterance, cumulative, both, 경고가 없으면 null이다.
같은 기준 초과 구간에서는 하나의 이벤트를 갱신하고 알림을 반복 생성하지 않는다. 기준 아래로 내려갔다가 다시 넘으면 새 이벤트를 만든다.

개별 근거 기준보다 낮은 발화라도 누적 경고에 기여했다면 근거 묶음에 보존한다. 묶음에는 최초 경고 계산 내역, 발화 revision, 점수·가중치, 정책 버전과 최고 누적값을 남긴다. 대표 근거는 계산상 기여도로 고르고 안내 문구는 템플릿으로 만든다. 별도 설명 LLM을 추가하지 않는다.

## 5. 앱 API와 결과

### 5.1 전송

초기에는 발화별 POST가 완료 결과를 응답한다. 앱 녹음·STT와 전송 작업은 분리한다. 같은 통화의 전송 큐는 한 번에 한 발화를 처리하고 다른 통화는 병행할 수 있다.

지연이 발화 생성 속도를 따라가지 못하면 접수 202 + 영속 작업 큐 + 결과 조회/통지를 도입한다. WebSocket만 추가해서 모델 처리량 문제가 해결되지는 않는다.

현재 보정 엔진은 동기식이므로 일반 def 경로 또는 별도 실행 경계를 사용한다. async 경로 안에서 동기 추론을 직접 실행하지 않는다. 동시 추론 수와 대기열 용량은 제한하고 실제 CPU/GPU 성능으로 정한다.

### 5.2 엔드포인트 제안

| API | 역할 |
|---|---|
| POST /api/v1/conversations | 통화 세션 생성·재접속 |
| POST /api/v1/utterances | 신규 발화 처리, 동일 발화 재시도 |
| GET /api/v1/conversations/{id}/utterances/{uid} | 해당 발화 최신 유효 revision의 상태·결과 |
| GET /api/v1/conversations/{id}/risk | 최신 통화 점수·경고·state_version |
| GET /api/v1/conversations/{id}/evidence | 통화 근거·이벤트 페이지 조회 |
| PATCH /api/v1/conversations/{id}/utterances/{uid} | 명시적 내용 정정 및 재분석 |
| POST /api/v1/conversations/{id}/end | 대기열 처리 후 통화 종료 |
| GET /health | 프로세스 생존 확인 |
| GET /ready | DB·모델·tokenizer·설정 준비 확인 |

기존 context 조회는 개발/진단용으로 유지할 수 있고 동일 소유자에게만 허용한다. 외부 소비자가 이미 있다면 응답 계약 변경은 /api/v2로 분리한다.

세션 생성은 인증 주체 + 앱의 client_session_id UUID로 중복 제거한다. 서버는 conversation_id UUID를 발급한다. 현재 앱의 날짜·분 단위 폴더명은 서버 ID와 매핑하여 단말 간 충돌을 방지한다.

일반 POST는 기존 여섯 필드를 유지하고 첫 revision을 서버가 1로 부여한다.

```json
{
  "schema_version": "1.0",
  "conversation_id": "18b52ae3-75a2-4dce-ae5f-572031f8ad22",
  "utterance_id": 4,
  "masked_text": "[PERSON] 씨 지금 안전 계자로 이채하세요",
  "has_masked_data": true,
  "masked_types": ["PERSON"]
}
```

### 5.3 응답 제안

AI 상세 설계서 6장의 필드를 analysis에 담고, 서버 식별·처리 정보를 바깥에 둔다. 이는 서버용 포장 제안이며 AI 모듈의 실제 Python 반환 클래스는 인수 후 맞춘다.

다음 수치는 계약 설명용 가상 값이다. 앞선 3개 발화는 누적 제외 기준 이하이고 과거 경고가 없는 상황을 가정한다.

```json
{
  "schema_version": "1.0",
  "conversation_id": "18b52ae3-75a2-4dce-ae5f-572031f8ad22",
  "utterance_id": 4,
  "revision": 1,
  "state_version": 4,
  "processing_status": "completed",
  "cached": false,
  "analysis": {
    "analysis_status": "ok",
    "current_text": "[PERSON] 씨, 지금 안전계좌로 이체하세요.",
    "current_risk_score": 93,
    "cumulative_risk_score": 93,
    "type_scores": {
      "institution_impersonation": 2,
      "money_transfer": 95,
      "personal_information": 3,
      "app_installation": 1,
      "secrecy": 2,
      "threat_pressure": 5,
      "loan_fraud": 1,
      "information_probing": 2
    },
    "detected_types": ["money_transfer"],
    "warning": {
      "status": "active",
      "reason": "single_utterance",
      "message": "송금 요구가 감지되었습니다."
    },
    "evidence": {
      "recent": {
        "utterance_id": 4,
        "revision": 1,
        "text": "[PERSON] 씨, 지금 안전계좌로 이체하세요.",
        "risk_score": 93,
        "risk_types": ["money_transfer"]
      },
      "highest": {
        "utterance_id": 4,
        "revision": 1,
        "text": "[PERSON] 씨, 지금 안전계좌로 이체하세요.",
        "risk_score": 93,
        "risk_types": ["money_transfer"]
      },
      "cumulative_events": []
    }
  },
  "model_info": {
    "model_version": "example-model-v1",
    "policy_version": "example-policy-v1",
    "probability_calibrated": false
  },
  "request_id": "example-request-id"
}
```

전체 history와 저장 경로 saved_as는 일반 앱 응답에 필요하지 않다. 근거 이벤트가 많아지면 응답은 요약·페이지 정보만 보내고 evidence 조회로 전체를 제공한다. 분석의 과거 스냅샷 state_version과 최신 통화 상태를 구분하여 앱에서 오래된 재전송 응답이 최신 경고를 덮어쓰지 않게 한다.

신규 완료는 201, 완료 재사용은 200이다. cached는 재사용 여부이고 completed는 처리 완료 여부다.

처리 실패는 공통 오류(code, retryable, request_id)와 발화별 처리 상태를 반환한다. 소유권·형식 검증 전에 거절된 요청에는 분석 객체를 만들지 않는다. 접수 후 모델 실패 응답·조회에는 analysis_status=error, 해당 시점의 점수와 유형 결과=null을 사용하고 기존 경고·근거는 보존한다. 마지막 유효 통화 상태는 last_valid_state에 as_of_utterance_id, state_version, calculated_at을 붙여 구분한다.

- 일시적 모델 장애/자원 부족: 503 또는 외부 추론 502, 제한된 재시도.
- 모델 입력 길이 초과: 422 INPUT_TOO_LONG, 자동 재시도하지 않고 명시적 정정 필요.
- 같은 키·다른 본문: 409 IDEMPOTENCY_CONFLICT.
- 순서 누락: 409 OUT_OF_ORDER 및 expected_utterance_id.
- 동일 요청 처리 중: 409 UTTERANCE_IN_PROGRESS 및 조회 안내.
- 정정 경합: 409 REVISION_CONFLICT.

## 6. 처리 순서·중복·복구·정정

```text
received → correcting → corrected → context_ready
         → scoring → scored → applying_policy → completed
```

각 단계에는 실패 코드·재시도 가능 여부·마지막 성공 단계를 별도로 기록한다.

1. 인증·입력 검증 후 통화 Lock을 확보하고 요청 키와 정규화 본문 해시를 저장한다.
2. 동일 키·동일 내용이면 진행 상태를 확인해 완료 결과 재사용 또는 마지막 성공 단계 재개.
3. 동일 키·다른 내용은 POST로 덮어쓰지 않는다. 수정은 PATCH로만 수행.
4. 새 발화는 1부터 순서대로 처리한다. 문맥 진행 위치와 분석·정책 완료 위치는 분리하여 저장한다.
5. 보정 결과·문맥 스냅샷·모델 점수를 단계별로 저장하여 장애 후 재사용한다.
6. 정책 계산은 현재까지 저장된 동일 버전의 유효 점수로 수행한다.
7. 누적 스냅샷·경고 이벤트·근거·통화 진행 위치·응답 결과는 하나의 짧은 트랜잭션으로 게시한다.
8. 같은 발화를 두 번 누적하지 않도록 단계 결과에 유일 키를 두고, 통화 state_version 비교 후 갱신한다.
9. 모델 호출 중에는 DB 쓰기 트랜잭션을 유지하지 않는다.
10. 재시작 시 실행 중 단계는 복구 대상으로 바꾸고 재전송 또는 복구 작업이 저장된 단계부터 재개한다.

LLM 응답 직후 저장 전에 프로세스가 종료되면 호출이 반복될 수 있다. 외부 호출의 절대적 1회 실행을 보장한다고 표현하지 않는다. 저장 완료 결과와 정책 반영의 중복 방지를 보장한다.

프로토타입은 해결되지 않은 발화 뒤의 처리·전송을 보류하고 앱 녹음은 로컬에 계속 저장한다. 무한 자동 재시도 대신 제한 횟수 후 지연/조치 필요 상태를 표시한다. 누락을 허용한 실시간 운영 정책은 별도 합의 없이 추가하지 않는다.

### 정정

정정은 새 발화가 아니라 동일 utterance_id의 새 revision이다.
PATCH에는 expected_revision, 새 마스킹 입력, 멱등성 키를 요구한다. 재전송은 같은 정정 결과를 반환하고, 오래된 revision을 기준으로 한 수정은 충돌로 거부한다.

원래 POST 요청의 중복 판별 기록은 정정 후에도 보존한다. 오래된 본문 재전송은 과거 결과를 조회하는 동작일 뿐, 현재 유효 revision을 되돌리지 않는다.

- 해당 발화의 보정·추론을 다시 수행한다.
- 변경된 발화를 history로 사용한 후속 발화도 재추론한다.
- 초기 구현은 단순성과 정확성을 위해 정정 지점부터 최신까지 순서대로 재생한다.
- 누적 창 밖이라도 과거 최고 근거·경고 이력에 영향이 있을 수 있어 통화 상태를 다시 계산한다.
- 정정 이전 스냅샷과 이벤트는 감사 이력으로 보존하고 최신 유효 상태에서 제외한다.
- 재생 중에는 새 발화 처리를 대기시키고 기존 유효 상태에 갱신 대기 표시를 한다.
- 부분 재생 결과를 최신 상태로 노출하지 않는다. 재생 완료 후 새 generation/state_version으로 게시한다.
- 재생 실패 시 이전 generation을 보존하고 재시도할 수 있어야 한다.

문서에 필요한 정정 동작은 현재 파일 저장의 동일 키 불변 정책만으로는 지원되지 않는다. revision별 불변 결과와 최신 유효 포인터를 분리한다. 통화 종료 후 정정은 이력을 갱신하되 실시간 경고 알림을 재활성화하지 않는다.

## 7. 저장 구조와 모델 생명주기

초기 SQLite 제안. 이 설계 작업에서는 DB 파일을 생성하지 않는다.

| 저장 대상 | 주요 내용 |
|---|---|
| conversations | owner, client_session_id, 활성/종료, 문맥 위치, 분석 위치, state_version, active_generation |
| utterance_revisions | 통화·발화·revision, 입력 해시·마스킹 본문, 현재 유효 여부, 처리 단계 |
| correction_results | revision별 검증된 보정 결과와 보정 설정 버전 |
| context_snapshots | current/history의 ID·revision, 불변 문맥 |
| model_scores | 모델 점수 1+8, 실제 사용한 문맥, 모델·전처리 버전 |
| risk_snapshots | 최근 창의 발화 목록·점수·누적값·정책 버전·계산 시각 |
| warning_events | 이벤트 ID, 최초/최근 시점, 활성/정정 상태, 사유, 최초 계산 내역 |
| evidence | 발화 revision과 이벤트 연결, 점수·가중치·유형, 유효 여부 |
| result_snapshots | 앱 응답 스냅샷, 생성 당시 state_version |
| revision_requests | 정정 멱등성 키·요청 해시·결과 revision·재생 진행 상태 |

revision별 입력 유일 키는 (conversation_id, utterance_id, revision)이다. 모델 실행 결과·정책 스냅샷은 실행 버전/generation을 추가하여 정정 이력과 분리한다.

모든 성공 점수를 저장해야 한다. 50점 이상 근거만 저장하면 25점 발화 여러 개의 누적을 복구할 수 없다. 메모리 버퍼는 캐시로만 사용한다.

첫 배포는 Uvicorn 단일 worker + 통화별 Lock이다. SQLite 쓰기 트랜잭션은 짧게 유지한다. 여러 worker/서버로 확장할 때는 프로세스 내 Lock을 DB 선점/통화별 큐로 바꾼다.

모델은 서버 시작 시 준비하고 요청마다 다시 로드하지 않는다. 준비 과정에서는 학습된 두 Head가 포함된 checkpoint, tokenizer 설정, label mapping, 모델 버전을 검증한다. 기본 KoELECTRA만 로드해 서비스 모델 준비 완료로 판단하지 않는다. /health와 /ready를 구분하고 실제 모델 준비 실패 시 분석을 503으로 거부한다.

합성 모델은 명시적인 개발 모드에서만 사용한다. 운영 모델 장애를 합성 점수로 대체하지 않는다. 한 통화는 시작 시 선택한 모델/정책 버전을 유지하여 점수와 근거를 재현할 수 있게 한다. 버전 변경 후 재분석은 별도 generation으로 처리한다.

통화 종료는 신규 발화를 막고 실시간 알림을 종료한다. 점수·근거는 보존 정책 내에서 조회한다. 보존 기간, 인증 발급 방식, 배포 장비는 후속 운영 설정으로 확정한다.

## 8. 기존 backend 재작성 범위

**제안: models는 재사용하고, backend는 전체 발화 처리 서비스를 중심으로 재구성한다. 기존 코드 삭제는 현재 승인된 작업이 아니다.**

| 현재 코드 | 판단 |
|---|---|
| models/llm_correction | 보정 엔진·마스킹 계약 재사용 |
| models/context_manager | 병합·최대 5개 history 구성 재사용 |
| backend/api/routes.py, schemas.py | AI 결과·세션·정정 계약에 맞춰 재작성 |
| backend/services/correction_pipeline.py | 보정→문맥 규칙 참고, UtteranceService 단계로 재구성 |
| backend/storage/context_store.py | 파일 복구 규칙 참고, DB Repository로 전환 제안 |
| backend/errors.py, config.py, dependencies.py | 책임 유지, 모델 준비·오류·정책 설정 확장 |
| tests/test_backend_* | 순서·중복·복구 시나리오 보존, 이전 파일 경로/응답 모양 의존 수정 |

현재 backend에는 위험 점수 누적·경고 보존·revision 재계산이 없다. 기능을 그대로 두고 마지막에 AI 호출만 추가하면 요구사항을 충족하기 어렵다.

```text
backend/
  api/                 # HTTP 계약
  services/
    utterance_service.py
    revision_service.py
  policies/
    conversation_risk.py
    warning.py
  storage/
    repository.py
    sqlite_repository.py
  schemas.py
  config.py
  dependencies.py      # AI 어댑터·모델 로딩
  errors.py
  main.py
models/
  llm_correction/
  context_manager/
  <개발 중인 위험감지 패키지>/
```

기존 코드·테스트를 참고 자료로 보존한 상태에서 새 계약을 구현하고 검증한 후 사용하지 않는 코드를 정리한다.

## 9. 앱 변경과 구현 순서

현재 작업 트리 기준 앱은 unmasked 발화를 로컬에 저장한다. 저장 JSON에는 raw_text가 있고 schema_version은 없다. INTERNET 권한과 서버 통신 구현도 추가가 필요하다.

- 전송 DTO는 별도로 만들어 raw_text를 제외하고 schema_version을 포함한다.
- 마스킹 성공 여부를 has_masked_data와 구분한다. false는 개인정보 미검출을 뜻하며 마스킹 미실행을 뜻하지 않는다.
- 로컬 ID와 서버 ID 매핑, 전송 본문·재시도 상태를 대기열에 영속화한다.
- 현재 발화 점수, 최근 20개 누적 점수, 과거 경고·최근/최고 근거를 각각 표시한다.
- 경고 확인과 경고 기록 삭제를 구분한다.
- revision과 state_version으로 늦은 응답의 덮어쓰기를 막는다.
- 실패는 분석 불가/갱신 대기로 표시하고 기존 경고를 유지한다.
- 대기열 크기·재시도 횟수를 제한하고 초과·지연을 표시한다. 발화를 조용히 버리지 않는다.

구현 순서:
1. AI 패키지 실제 추론 진입점·checkpoint·반환 단위 확인, 어댑터 계약 확정.
2. DB Repository와 버전·단계·중복 규칙 구현.
3. 보정→문맥→발화 추론 연결.
4. 최근 20개 정책·경고·근거 저장과 결과 응답 구현.
5. Android 전송 큐·결과 화면 연결.
6. 정정 재생·종료 후 조회까지 구현하고 통합 검증.

핵심 검증:
- 두 통화 문맥과 점수의 격리.
- 같은 발화 재전송 시 모델 결과 재사용 및 누적·이벤트 중복 방지.
- 일부 단계 저장 후 서버 종료 시 복구.
- 현재 최대 6개 텍스트와 최근 20개 점수 범위 구분.
- 문서의 누적 계산 예시와 경고 재진입 사례.
- 92점 발화가 창에서 빠진 뒤 과거 근거 보존.
- 저장 기준 미만 발화들이 만든 누적 경고 근거 보존.
- 독립된 8개 Head 결과를 임의로 지우지 않는지 확인.
- history 토큰 초과와 current 단독 초과의 구분.
- 실패 점수 null, 이전 유효 상태의 계산 시점 표시.
- 과거 발화 정정으로 후속 점수·최고 근거·경고가 함께 정정되는지 확인.
- 재생 중 실패와 재전송 후 유효 generation 보존.
- 잘못된 소유자의 세션 조회/수정 거부.
- 실제 발화 간격 대비 추론 P95 지연·대기열 증가량 측정.

## 10. 자료와 미확정 항목

- [AI 구현 요약 및 멘토링 질문](https://docs.google.com/document/d/1yS6BweJlHB5hZ6w8HWgcZSsKSiqWWsqjONXG2_XL8b0/edit?tab=t.0): 현재 모델·전처리·8개 유형·구현 상태.
- [AI 상세 설계서 4장](https://docs.google.com/document/d/1CngNc3P9bCjZGCkEY__uRa64vGgvccECeODuaSZyuas/edit?tab=t.i124d8yc3b98): 모델 출력과 점수 단위.
- [AI 상세 설계서 5장](https://docs.google.com/document/d/1CngNc3P9bCjZGCkEY__uRa64vGgvccECeODuaSZyuas/edit?tab=t.cie1t6a499y8): 누적·경고·근거·정정.
- [AI 상세 설계서 6장](https://docs.google.com/document/d/1CngNc3P9bCjZGCkEY__uRa64vGgvccECeODuaSZyuas/edit?tab=t.y3j17zxkm1dd): 결과 JSON.
- [기존 업무 파이프라인](https://docs.google.com/document/d/1iraB3UKo0P8YP3wJzTXLhQbzzlU_uPpFYzgjEa50mMI/edit): 전체 앱→서버 구간. 이전 6개 라벨보다 새 AI 문서의 8개 라벨을 적용한다.
- [FastAPI 동시성](https://fastapi.tiangolo.com/async/) 및 [SQLite 트랜잭션](https://www.sqlite.org/lang_transaction.html): 실행·저장 경계 참고.

확정: 발화 모델 + 최근 20개 누적이라는 사용자 선택, 문서상의 모델 입력과 8개 출력 유형.
서버 제안: REST, SQLite, API 포장, 서버 상태 소유권, revision/generation 저장 방식.
추가 확인: AI 실제 호출 함수·학습 체크포인트·배포 장비, 원본 수식/정책 코드, 검증 후 임계값, 데이터 보존 및 인증 운영 설정.
