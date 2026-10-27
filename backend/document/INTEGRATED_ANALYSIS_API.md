# 발화 통합 분석 API

`POST /api/v1/utterances/analyze`는 마스킹 발화를 받아 보정·AI 분석·누적 계산·경고·저장을 수행한다. 서버 실행과 전체 API 목록은 [시작 안내](README.md), 공통 저장·종료 규칙은 [계산·저장 API](ANALYSIS_API.md)를 참고한다.

## 입력과 응답

```json
{
  "schema_version": "1.0",
  "conversation_id": "integrated-test-001",
  "utterance_id": 1,
  "masked_text": "안녕하세요",
  "has_masked_data": false,
  "masked_types": []
}
```

요청은 위 여섯 필드만 받는다. `raw_text` 같은 추가 필드는 허용하지 않는다. 같은 통화에서 `utterance_id`는 1부터 연속으로 전송하고, 서버가 같은 발생 순서의 `sequence`를 부여한다. 보정 전용 `/api/v1/utterances`는 제거했다.

응답은 `CalculationPreviewResponse`다. 현재·누적·유형별 점수는 0~100이며, 정상 시작 시 등록되는 경고 모듈의 `warning`·`evidence`를 포함한다. 개발용 결과 입력과 같은 저장소를 사용하므로 테스트 목적별로 통화 ID를 구분한다.

## 처리 순서와 책임

1. `validate_utterance()`로 마스킹 계약을 검사한다.
2. 해당 통화 잠금을 잡고 저장 파일을 읽는다. 종료·이전 실패·순서 오류가 있으면 외부 모델 호출 전에 차단한다. 이 요청에 사용할 경고 설정도 준비한다.
3. `CorrectionEngine.correct()`로 현재 발화를 보정하고, `merge_utterance()`로 입력과 보정 결과를 병합·검증한다.
4. 저장 기록에서 이전 최대 5개의 보정 문장을 오래된 순서대로 꺼내 현재 문장과 함께 AI 입력을 만든다.
5. `_run_ai()`가 등록된 분석기를 호출한다. 현재 점수, 8개 유형 점수와 감지 유형을 검증한다. AI 오류는 실패 결과 객체로 바꾼다.
6. 분석 서비스가 현재 포함 최근 20개 성공 발화의 누적 위험도를 계산한다. 현재 분석이 실패했다면 계산 결과는 `None`이다.
7. 경고 모듈에 현재 분석·계산·직전 상태·설정을 전달하고 반환 계약을 검사한다.
8. 입력·응답·갱신 상태를 같은 통화 파일에 저장한 다음 응답한다.

AI 문맥은 별도 메모리 버퍼가 아니라 저장된 문장에서 구성한다. 재시작 후에도 이어서 처리할 수 있다. 통화 전체 이력을 다시 메모리 저장소에 삽입하지 않고, 계산에 필요한 최근 창만 변환한다.

같은 통화는 보정·AI 호출부터 저장까지 순차 처리한다. 다른 통화의 보정·저장은 독립적으로 진행한다. 공유 KoELECTRA 모델·토크나이저는 어댑터의 추론 잠금으로 보호하므로 AI 추론 호출 자체는 하나씩 실행한다. 현재 잠금과 JSON 저장은 단일 worker 기준이다.

## AI 어댑터와 시작 과정

`backend/services/ai_service.py`의 `RiskAnalyzer` 계약:

- `model_version`: 비어 있지 않은 모델 버전, 최대 120자
- `analyze(model_input: RiskModelInput) -> RiskModelScores`
- 입력: `current_text`, 이전 최대 5개 문장인 `history_texts`
- 출력: 0~1 `is_phishing_score`, 8개 전체 `type_scores`, 현재 감지 유형 `detected_types`

`KoElectraRiskAnalyzer`는 이 입력을 `risk_speech_ai.inference.InferenceInput`으로 변환한다. 예측 결과가 한 개의 `InferenceOutput`인지 확인하고 위험·유형 확률을 서버 계약으로 변환한다. 감지 유형은 AI 추론 계층의 결과를 사용하며, 과거 발화의 유형을 복사하지 않는다.

`lifespan()`은 `PIC_AI_MODE`에 따라 AI를 한 번 준비하고 `app.state.risk_analyzer`에 등록한다.

| 모드 | 시작 과정 |
|---|---|
| `disabled` | AI를 등록하지 않고 경고 모듈만 등록 |
| `development` | `load_development_analyzer()`로 사전학습 인코더·학습 전 판단층을 준비. `.pt` 불필요 |
| `checkpoint` | `load_risk_analyzer()`에 `PIC_AI_CHECKPOINT`, `PIC_AI_MODEL_VERSION`을 전달 |

`PIC_AI_MODE`가 없을 때만 기존 `PIC_AI_ENABLED`를 사용한다. `0` 기본값은 `disabled`, `1`은 `checkpoint`와 같다. 명시한 모드가 기존 설정보다 우선하며 잘못된 설정이나 모델 준비 실패는 서버 시작을 중단한다.

두 AI 모드 모두 같은 `KoElectraRiskAnalyzer`를 사용하므로 이후 계산·경고·저장 흐름은 동일하다. 체크포인트 모드는 토크나이저·모델 메타데이터 검증을 통과해야 시작하며, 이미 읽은 체크포인트를 추론 생성 과정에 전달하여 파일을 중복해서 읽지 않는다.

개발 모드의 판단층은 학습되지 않았다. 점수와 경고는 연결 확인용이며 탐지 정확도 평가에 사용할 수 없다. 개발 모델 버전은 `development-untrained-...` 형식으로 실행마다 생성된다. 재시작 또는 모드 변경 이후에는 새 통화 ID를 사용해 서로 다른 모델의 결과가 같은 검증 통화에 섞이지 않게 한다. 학습 완료 체크포인트를 받은 뒤에는 체크포인트 모드로 전환하고 별도로 실제 추론을 검증한다.

통합 API는 AI 객체가 없으면 LLM 호출 전에 503을 반환한다. LLM 키나 호출 성공 여부는 첫 보정 요청에서 확인되며 `/health/ready`가 이를 보장하지 않는다.

## 개발 모드 수동 검증

프로젝트 최상위 폴더에서 다음 명령으로 시작한다. 서버 환경에 사용 가능한 `OPENAI_API_KEY`가 설정되어 있어야 발화 보정이 가능하다. 모델·토크나이저가 캐시되어 있지 않다면 최초 실행에 리소스 다운로드가 필요하다.

```powershell
$env:HF_HUB_CACHE = "$PWD\hf-cache\hub"
$env:PIC_AI_MODE = "development"
.\.venv-ai\Scripts\python.exe -B -m uvicorn backend.main:app --reload
```

위 캐시 설정은 프로젝트의 `hf-cache/hub`에 준비한 리소스를 재사용한다. `hf-cache/`는 Git에서 제외되며, 환경 변수는 현재 PowerShell 세션에만 적용되므로 새 터미널에서는 다시 설정해야 한다.

1. `GET /health/ready`에서 HTTP 200, `ai_ready=true`, `warning_ready=true`, `ai_mode="development"`, `model_version="development-untrained-..."`를 확인한다. 모델 버전의 뒤쪽 값은 실행마다 다르다. 시작 준비가 끝나기 전에는 요청을 받지 않는다.
2. `http://127.0.0.1:8000/docs`에서 `POST /api/v1/utterances/analyze`에 아래 발화를 보낸다. `conversation_id`는 이번 실행에서 처음 쓰는 값으로 바꾼다.

```json
{
  "schema_version": "1.0",
  "conversation_id": "development-test-001",
  "utterance_id": 1,
  "masked_text": "안녕하세요. 오늘 일정 확인하려고 전화했어요.",
  "has_masked_data": false,
  "masked_types": []
}
```

3. 응답에 `analysis_status="ok"`, 점수·계산 내역·`warning`·`evidence`가 포함되는지 확인한다. 모델 버전은 분석 응답 필드가 아니며 `/health/ready`와 저장된 입력 기록에서 확인한다. 같은 통화 ID에서 `utterance_id=2`, 새로운 문장으로 다시 요청하면 저장된 첫 문장이 AI 문맥에 포함되고 두 발화로 누적 계산된다. 점수나 경고의 크기 자체를 정답 기준으로 삼지 않는다.
4. `GET /api/v1/dev/model-results?conversation_id=development-test-001`로 최신 응답을 조회한다. `&utterance_id=1`을 추가하면 첫 응답을 조회할 수 있다. 테스트에서 사용한 통화 ID로 바꿔 조회한다.
5. AI 분석이 실패해 `analysis_status="error"`로 저장된 경우에만 [실패와 재시도](#실패와-재시도)의 `POST /api/v1/utterances/analyze/retry`를 사용한다. 요청에는 이번 통화 ID와 마지막 실패 발화 ID를 넣는다. 모두 성공했다면 재시도 단계는 생략한다. LLM 보정 실패는 저장된 AI 실패가 아니므로 원래 분석 요청을 다시 보낸다.
6. `POST /api/v1/conversations/end`에 아래 통화 ID를 보내 종료한다. 이후 신규 분석·재시도는 409로 차단되고 저장된 결과 조회는 유지된다.

```json
{
  "conversation_id": "development-test-001"
}
```

수동 검증은 실제 LLM 보정 호출과 개발 모델 추론을 사용한다. 아래 자동 테스트의 대체 객체 검증과 구분한다. 통화 종료 시 활성 경고 이벤트를 닫고 미확인 알림을 만료하며, 종료용 `warning`·`evidence`를 반환한다. 과거 발화 조회 응답은 그대로 보존한다.

통화 중 경고가 발생하면 `GET /api/v1/notifications?conversation_id=development-test-001`로 미확인 알림을 확인할 수 있다. 조회에서 받은 `event_id`와 통화 ID를 `POST /api/v1/notifications/ack`로 보내면 확인 상태가 저장된다. 조회만으로 확인 처리하지 않으며 앱 연결·중복 표시 방지는 별도로 구현해야 한다. [알림 계약](ANALYSIS_API.md#알림-조회수신확인)을 참고한다.

## 실패와 재시도

| 상황 | 처리 |
|---|---|
| AI 미등록 | 503, 보정 호출 없음 |
| 마스킹 계약 오류 | 422, 모델 호출·저장 없음 |
| 중복·순서·이전 실패·종료 충돌 | 409, 모델 호출·저장 없음 |
| LLM 보정 실패 | 502, 순서 진행·분석 기록 저장 없음 |
| AI 추론 실패·잘못된 출력 | 실패 저장, HTTP 200 및 `analysis_status="error"`, 점수 `null` |
| 저장소 읽기·쓰기 실패 | 503, 기존 파일 유지 |
| 경고 모듈 예외·반환 계약 오류 | 503, 해당 발화 부분 저장 없음 |

FastAPI 의존성에서 AI 등록을 먼저 확인하므로 AI 미등록과 종료·순서 오류가 함께 있으면 503이 먼저 반환될 수 있다. AI 오류 로그에는 예외 클래스명을 기록하고 발화·예외 원문은 기록하지 않는다.

`POST /api/v1/utterances/analyze/retry` 요청:

```json
{
  "conversation_id": "integrated-test-001",
  "utterance_id": 1
}
```

통화의 마지막 실패 발화만 재시도한다. 저장된 보정 문장과 이전 문맥으로 AI만 다시 호출하므로 LLM 보정은 반복하지 않는다. 이전 실패를 이력에 보존하고 성공하면 후속 차단을 해제한다. 차단된 후속 요청은 호출자가 다시 전송한다.

개발용 `/api/v1/dev/model-results/retry`는 재분석 점수를 직접 받는 경로다. 저장 전에 실패한 신규 요청을 다시 보내면 보정·AI가 다시 호출될 수 있다. 완료 여부는 `GET /api/v1/dev/model-results`로 조회한다.

## 자동 검증

```powershell
.\.venv-ai\Scripts\python.exe -B -m unittest discover -s tests -p "test_integrated_analysis_api.py" -v
.\.venv-ai\Scripts\python.exe -B -m unittest discover -s tests -p "test_koelectra_analyzer.py" -v
.\.venv-ai\Scripts\python.exe -B -m unittest tests.test_development_mode_api -v
```

첫 테스트는 임시 저장소와 대체 LLM·AI 제공자로 서버 흐름을, 두 번째는 대체 예측기로 어댑터의 입력·확률 변환과 오류를 검사한다. 세 번째는 개발 모드 시작과 실제 개발 분석기·작은 메모리 모델을 거치는 API 흐름을 검사한다. 실제 OpenAI 호출, 모델 다운로드나 학습 완료 모델의 정확도 검증을 뜻하지 않는다.

2026-10-10에는 캐시된 실제 사전학습 KoELECTRA를 사용한 개발 모드도 별도로 실행 확인했다. FastAPI `TestClient`에서 실제 추론·어댑터·경고 모듈과 임시 JSON 저장소를 연결해 문맥 최대 5개·최근 20개 계산, 실패 저장·재시도·이력 보존, 조회·통화 종료 차단을 확인했다. LLM 보정은 대체 객체였으며 실제 OpenAI 호출과 학습 완료 `.pt` 검증은 남아 있다. 실행 범위·측정값과 실제 토크나이저 테스트 명령은 [사전학습 모델 실행 확인](README.md#사전학습-모델-실행-확인--2026-10-10)을 참고한다.
