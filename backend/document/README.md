# PIC 발화 분석 API 서버

> 프로젝트의 최신 목표 파이프라인은 [최상위 README](../../README.md)를 먼저 따른다. 이 문서는 서버의 현재 구현과 API 사용 안내이며, ElevenLabs STT 중계·별도 LLM 문맥 위험 판단·상시 운영 배포가 완료되었다는 뜻은 아니다.

앱이 보낸 마스킹 발화를 보정하고, AI 분석 결과로 누적 위험도를 계산한 뒤 경고·근거와 함께 JSON으로 반환한다. 통화별 분석 기록과 경고 상태는 JSON 파일로 보존한다.

이 문서는 현재 구현의 시작 안내다. 상세 계약은 [계산·저장 API](ANALYSIS_API.md), [통합 분석](INTEGRATED_ANALYSIS_API.md), [경고 연동](WARNING_INTEGRATION.md)을 참고한다. [초기 설계안](DESIGN.md)은 구현 전 제안으로, 현재 동작과 구분한다.

## 실행

프로젝트 최상위 폴더에서 기존 Python 3.11 환경을 사용한다.

```powershell
$env:HF_HUB_CACHE = "$PWD\hf-cache\hub"
$env:PIC_AI_MODE = "development"
.\.venv-ai\Scripts\python.exe -B -m uvicorn backend.main:app --reload
```

`HF_HUB_CACHE`는 프로젝트의 `hf-cache/hub`에 준비한 모델·토크나이저 캐시를 재사용하도록 지정한다. `hf-cache/`는 Git에서 제외되며 소스 코드와 함께 커밋하지 않는다. 위 환경 변수는 현재 PowerShell 세션에만 적용되므로 새 터미널에서도 프로젝트 최상위 폴더로 이동한 뒤 다시 설정한다.

- 실행 확인: `http://127.0.0.1:8000/health`
- Swagger: `http://127.0.0.1:8000/docs`
- AI·경고 객체 등록 확인: `http://127.0.0.1:8000/health/ready`

`development` 모드는 `.pt` 없이 개발용 AI와 실제 경고 모듈을 준비한다. 사전학습 KoELECTRA 모델·토크나이저 캐시가 없다면 첫 실행에 리소스 다운로드가 필요하다. 준비가 끝난 뒤 `/health/ready`는 `ai_mode="development"`, `model_version="development-untrained-..."`와 200을 반환한다. 모델은 서버 시작 시 한 번 준비하며 `--reload`로 프로세스가 재시작되면 다시 준비한다.

AI 리소스 없이 서버 계산·저장만 확인하려면 `PIC_AI_MODE="disabled"`로 실행한다. 이때 `/health`는 200, `/health/ready`는 `ai_ready=false`, `model_version=null`과 503을 반환하는 것이 정상이다. 개발용 결과 입력 API는 이 상태에서도 사용할 수 있다.

의존성은 서버용 `requirements.txt`, AI용 `requirements-ai.txt`, 테스트용 `requirements-dev.txt`로 구분한다. 새 환경을 구성할 때 필요한 목록을 설치한다. `.env` 파일 자동 로딩은 구현하지 않았으므로 실행할 프로세스의 환경 변수를 설정한다.

## 전체 처리 워크플로우

```text
앱: 마스킹한 현재 발화 전송
 → 입력 계약 확인
 → 해당 통화 잠금 획득 및 저장 기록 조회
 → 종료 여부·발화 순서·이전 실패·경고 설정 확인
 → LLM으로 현재 발화 보정
 → 현재 문장 + 이전 최대 5개 보정 문장 구성
 → 위험 탐지 AI 호출 및 출력 검증
 → 현재 포함 최근 20개 발화로 누적 위험도 계산
 → 실제 경고 모듈로 경고 상태·근거·안내 문구 갱신
 → 분석 결과·응답·경고 상태를 같은 통화 파일에 저장
 → 앱에 JSON 반환
```

서버는 저장이 완료된 뒤 응답한다. 보정 실패는 분석 기록을 추가하지 않는다. AI 분석 실패는 실패 기록을 남기고 점수를 `null`로 반환하며, 해당 발화를 복구하기 전까지 다음 발화를 차단한다.

처리에 사용하는 범위는 서로 다르다.

| 용도 | 범위 |
|---|---|
| AI 문맥 | 현재 발화 + 이전 최대 5개 |
| 누적 위험도 | 현재 발화 포함 최근 20개 |
| 조회·재시도 이력·경고 근거 | 통화 전체 |

같은 통화의 처리와 종료는 잠금으로 순서를 보장한다. 서로 다른 통화의 보정·저장은 독립적으로 진행하고, 공유 KoELECTRA 모델의 추론 호출만 어댑터 내부 잠금으로 직렬화한다. 처리·대기가 끝난 통화 잠금은 제거한다. 잠금은 프로세스 내부에 있으므로 **Uvicorn 단일 worker**로 실행한다.

## API 목록

| 메서드·경로 | 역할 |
|---|---|
| `GET /health` | 서버 응답 확인 |
| `GET /health/ready` | AI·경고 객체 등록 여부, AI 모드·모델 버전 확인 |
| `POST /api/v1/utterances/analyze` | 마스킹 발화 보정·AI 분석·계산·저장 |
| `POST /api/v1/utterances/analyze/retry` | 마지막 실패 발화를 저장된 문장으로 AI 재분석 |
| `POST /api/v1/dev/model-results` | 샘플 AI 결과를 직접 입력해 계산·저장 |
| `POST /api/v1/dev/model-results/retry` | 마지막 실패 발화의 재분석 결과 직접 등록 |
| `GET /api/v1/dev/model-results` | 최신 또는 특정 발화의 저장 응답 조회 |
| `POST /api/v1/conversations/end` | 통화·경고 이벤트 종료, 미확인 알림 만료, 최종 경고 반환 |
| `GET /api/v1/notifications` | 통화별 미확인 알림 조회 |
| `POST /api/v1/notifications/ack` | 알림 수신확인·반복 확인 요청 처리 |

보정 전용 `POST /api/v1/utterances`는 제거했다. 발화 입력은 통합 분석 API를 사용한다. 개발용 결과 입력 API는 서버 계산 검증용이며 앱의 실제 AI 판정을 대신하는 경로가 아니다.

## AI 설정과 현재 구현 상태

| 환경 변수 | 용도 |
|---|---|
| `HF_HUB_CACHE` | Hugging Face 모델·토크나이저 캐시 경로. 현재 프로젝트의 `hf-cache/hub` 사용 |
| `PIC_AI_MODE` | `disabled`, `development`, `checkpoint` 중 선택 |
| `PIC_AI_ENABLED` | `PIC_AI_MODE`가 없을 때만 사용하는 기존 설정. `0` 기본값은 비활성화, `1`은 체크포인트 모드 |
| `PIC_AI_CHECKPOINT` | 체크포인트 모드에서 필요한 `.pt` 경로 |
| `PIC_AI_MODEL_VERSION` | 체크포인트 모드에서 필요한 모델 버전, 1~120자 |
| `OPENAI_API_KEY` | 통합 분석의 LLM 보정에 필요한 서버용 키 |
| `OPENAI_MODEL` | 보정 모델 선택 |
| `OPENAI_TIMEOUT_SECONDS`, `OPENAI_MAX_RETRIES`, `OPENAI_MAX_OUTPUT_TOKENS` | 보정 호출 제한 |

명시한 `PIC_AI_MODE`가 기존 `PIC_AI_ENABLED`보다 우선한다. 두 변수가 모두 없으면 비활성화 모드다. 잘못된 모드 또는 체크포인트 모드의 필수 설정 누락은 서버 시작을 중단한다. 개발 모드에는 체크포인트 경로나 별도 모델 버전 설정이 필요하지 않다.

학습된 체크포인트를 받은 뒤에는 다음처럼 실행한다. 로더는 CPU로 모델을 준비하며 체크포인트의 모델·라벨·토크나이저 정보가 저장소 계약과 호환되는지 검사한다.

```powershell
$env:PIC_AI_MODE = "checkpoint"
$env:PIC_AI_CHECKPOINT = "C:\models\trained-model.pt"
$env:PIC_AI_MODEL_VERSION = "trained-v1"
.\.venv-ai\Scripts\python.exe -B -m uvicorn backend.main:app --reload
```

체크포인트 경로와 버전은 실제 전달받은 파일에 맞춘다. 토크나이저·모델 캐시가 없다면 체크포인트 모드에서도 사전학습 리소스가 필요할 수 있다.

`DefaultWarningManager`는 모든 모드에서 서버 시작 시 등록된다. 개발 모드의 `development_analyzer.py`는 사전학습 인코더에 새로 초기화한 판단층을 사용한다. 실제 추론 경로를 연결하지만 점수·위험 유형·경고 내용으로 탐지 성능을 평가할 수 없다. 서버를 다시 시작할 때 판단층과 개발 모델 버전이 달라지므로 재시작하거나 AI 모드를 바꾼 뒤에는 새 통화 ID로 검증한다.

`/health/ready`는 객체 등록만 확인한다. OpenAI 키·잔액이나 실제 추론 성공까지 검사하지 않는다. 실제 발화 분석에는 사용 가능한 `OPENAI_API_KEY`가 필요하다. [통합 분석 검증 순서](INTEGRATED_ANALYSIS_API.md#개발-모드-수동-검증)에 따라 보정부터 저장까지 확인한다. 개발 모드 연결 구현과 학습 완료 모델의 실제 추론·성능 검증은 구분한다.

## 주요 코드

| 파일 | 주요 함수·역할 |
|---|---|
| `backend/main.py` | HTTP 요청·응답과 오류 상태 코드 |
| `backend/lifespan.py` | `lifespan()`: AI·경고 객체 준비 |
| `backend/services/development_analyzer.py` | `load_development_analyzer()`: 체크포인트 없는 개발용 AI 준비 |
| `backend/services/ai_loader.py` | `load_risk_analyzer()`: 호환성을 검증한 체크포인트 AI 준비 |
| `backend/services/pipeline_service.py` | `analyze_utterance()`, `retry_utterance_analysis()`: 보정·AI·계산 연결 |
| `backend/services/utterance_service.py` | `validate_utterance()`, `get_correction_engine()`: 보정 공통 기능 |
| `backend/services/risk_service.py` | `build_model_result()`, `calculate_risk()`: 공통 입력·누적식 |
| `backend/services/analysis_service.py` | 결과 등록·재시도·조회·통화 종료 조율 |
| `backend/services/warning_service.py` | `update_warning()`: 경고 호출과 반환 계약 검증 |
| `backend/services/notification_service.py` | 알림 생성·조회·수신확인·종료 시 만료 |
| `backend/stores/analysis_file_store.py` | `load()`, `save()`: 파일 검증·원자적 교체 |
| `backend/stores/conversation_locks.py` | `ConversationLocks.hold()`: 통화별 처리 순서 보호 |

## 정리 후 회귀 검증

```powershell
.\.venv-ai\Scripts\python.exe -B -m unittest tests.test_analysis_api tests.test_integrated_analysis_api tests.test_lifecycle_analysis_api tests.test_warning_analysis_api tests.test_real_warning_api tests.test_server_cleanup -v
.\.venv-ai\Scripts\python.exe -B -m unittest tests.test_ai_loader tests.test_koelectra_analyzer -v
.\.venv-ai\Scripts\python.exe -B -m unittest tests.test_development_mode_api -v
.\.venv-ai\Scripts\python.exe -B -m unittest tests.test_notification_api -v
```

서버 검증은 임시 JSON 저장소와 대체 AI를 사용한다. 로더 검증은 메모리상의 작은 모델로 체크포인트 재읽기 방지·호환성·기존 모델 보호를 확인한다. 공통 입력·대체 객체는 `tests/api_helpers.py`, 작은 AI 모델·토크나이저는 `tests/ai_helpers.py`에 모았다. 현재 없는 서버 구조를 참조하던 `test_backend_api.py`, `test_backend_pipeline.py`는 제거했다.

개발 모드 테스트는 모드 선택·시작 실패·모델 1회 로딩·readiness와 실제 어댑터를 거치는 계산·저장·재시도·종료를 확인한다. 메모리에 만든 작은 Torch 모델로 `DevelopmentPredictor`의 실제 추론 경로도 실행한다. 전체 사전학습 모델 리소스를 내려받아 실행한 검증과는 구분한다.

실제 KoELECTRA 리소스가 필요한 통합 테스트와 `.pt`를 생성하는 학습·복원 테스트는 별도로 남아 있다. 위 명령은 모델 다운로드나 실제 학습 완료 모델의 성능 검증을 수행하지 않는다.

### 사전학습 모델 실행 확인 — 2026-10-10

다운로드한 캐시만 사용하도록 네트워크 접근을 끈 상태에서 실제 사전학습 인코더·개발용 판단층·어댑터를 FastAPI `TestClient`에 연결해 실행했다. LLM 보정은 대체 객체, 저장소는 임시 JSON 경로를 사용했다.

- 연속 21개 발화의 추론·계산·경고·저장, 이전 문맥 최대 5개와 최근 20개 계산 창 이동을 확인했다.
- 추론 시간 초과를 의도적으로 발생시켜 실패 저장·후속 차단·LLM 재호출 없는 실제 AI 재시도와 이전 실패 이력 보존을 확인했다.
- 결과 조회, 통화 종료 후 신규 분석·재시도 차단, 종료 후 조회와 서버 종료 시 참조 정리를 확인했다.
- 실제 토크나이저 통합 테스트 10개가 통과했다. 512토큰 경계와 오래된 문맥 제거 검증을 포함한다.

이 PC의 CPU에서 캐시 기반 시작은 약 13.78초, 짧은 합성 문장 21개의 API 요청은 중앙값 0.117초·최대 0.197초였다. 외부 LLM 호출을 제외한 단일 실행 측정이며 실제 통화 지연이나 탐지 성능을 의미하지 않는다. `.pt` 생성과 학습은 수행하지 않았다.

캐시가 준비된 환경에서 토크나이저 통합 테스트를 다시 실행할 수 있다.

```powershell
$env:HF_HUB_CACHE = "$PWD\hf-cache\hub"
.\.venv-ai\Scripts\python.exe -B -m unittest tests.test_koelectra_integration -v
```

## 저장과 남은 작업

`backend/data/analysis/<통화 ID의 SHA-256>.json`에 통화 상태, 계산 설정, 발화 입력·응답, 이전 실패 시도, 경고 상태, 최종 종료 결과, 알림 내용·수신 상태를 저장한다. 이 경로는 Git에서 제외되어 있다. 임시 파일 작성 후 교체하여 저장 실패 시 기존 기록을 보호한다.

2026-10-11 통화 종료·알림 조회·수신확인 연결 후 서버 API 회귀 71개와 알림·개발 모드 27개, 총 98개 테스트가 통과했다. 종료 시 경고 이력 보존, 미확인 알림 만료, 반복 확인, 동시 종료·확인, 저장 실패와 기존 파일 호환을 포함한다. 외부 OpenAI 호출이나 학습 완료 체크포인트는 사용하지 않았다.

현재는 통화 파일 전체를 읽고 교체한다. 여러 worker·여러 서버의 동시 저장은 지원하지 않는다. 실제 OpenAI 보정과 학습 완료 체크포인트를 함께 사용하는 통합 검증, 발화 정정에 따른 후속 재처리, 앱의 알림 조회·표시·수신확인 연결은 남은 작업이다. 앱은 `(conversation_id, event_id)`를 영속적으로 기록해 중복 표시를 막아야 한다. 이번 알림 API는 통화 화면용 조회 방식이며 FCM 등 백그라운드 푸시는 포함하지 않는다.
