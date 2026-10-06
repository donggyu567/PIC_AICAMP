from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from backend.schemas import (
    CalculationPreviewResponse,
    ConversationEndRequest,
    ConversationEndResponse,
    ModelResultRequest,
    UtteranceAnalysisRetryRequest,
    UtteranceRequest,
)
from backend.services.ai_service import RiskAnalyzer
from backend.services import analysis_service
from backend.services.warning_service import WarningIntegrationError
from backend.services.pipeline_service import analyze_utterance, retry_utterance_analysis
from backend.services.analysis_service import (
    AnalysisNotFoundError,
    get_analysis_result,
    process_model_result,
    retry_model_result,
)
from backend.stores.analysis_file_store import AnalysisStorageError
from backend.stores.analysis_store import AnalysisConflictError
from backend.services.utterance_service import (
    UtteranceOrderError,
    process_utterance
)
from models.context_manager import InputDataError
from models.warning_manager.warning_manager import WarningManager
from models.llm_correction import (
    ContractError,
    CorrectionValidationError,
    LLMClientError,
    LLMResponseError,
)

app = FastAPI(title="PIC API Server")


def get_risk_analyzer(request: Request) -> RiskAnalyzer:
    """실제 구현체는 서버 시작 시 app.state.risk_analyzer에 등록한다."""
    analyzer = getattr(request.app.state, "risk_analyzer", None)
    version = getattr(analyzer, "model_version", None)
    if (
        analyzer is None
        or not callable(getattr(analyzer, "analyze", None))
        or not isinstance(version, str)
        or not version.strip()
        or len(version) > 120
    ):
        raise HTTPException(status_code=503, detail="위험 탐지 AI가 연결되지 않았습니다.")
    return analyzer


def get_warning_manager(request: Request) -> WarningManager | None:
    """미연결 시 점수만 처리하며, 실제 구현체는 app.state에 등록한다."""
    manager = getattr(request.app.state, "warning_manager", None)
    if manager is not None and not callable(getattr(manager, "update_warning", None)):
        raise HTTPException(status_code=503, detail="경고 모듈 연결이 올바르지 않습니다.")
    return manager


@app.exception_handler(WarningIntegrationError)
async def handle_warning_error(request: Request, error: WarningIntegrationError):
    return JSONResponse(status_code=503, content={"detail": str(error)})


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post(
    "/api/v1/conversations/end",
    response_model=ConversationEndResponse,
    tags=["통화 관리"],
    summary="통화 종료 및 분석 기록 보존",
    description=(
        "저장된 통화를 종료합니다. 반복 요청은 최초 종료 시각을 반환합니다. "
        "실패 기록도 보존하며 종료 후 신규 분석·재시도는 차단합니다. "
        "기존 분석 결과는 계속 조회할 수 있습니다. "
        "AI·경고 모듈은 호출하지 않으며 경고 종료 이벤트 처리는 추후 연동합니다."
    ),
    responses={
        404: {"description": "저장된 통화 없음"},
        503: {"description": "분석 기록 읽기 또는 저장 실패"},
    },
)
def finish_conversation(payload: ConversationEndRequest):
    try:
        return analysis_service.end_conversation(payload.conversation_id)
    except AnalysisNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from None
    except AnalysisStorageError:
        raise HTTPException(
            status_code=503, detail="분석 기록을 읽거나 저장할 수 없습니다."
        ) from None


@app.post("/api/v1/utterances")
def receive_utterance(payload: UtteranceRequest):
    try:
        # 기존 보정 전용 경로도 종료된 분석 통화의 발화를 받지 않는다.
        with analysis_service.analysis_lock:
            snapshot = analysis_service.analysis_store.load(payload.conversation_id)
            analysis_service.ensure_conversation_active(snapshot)
            correction = process_utterance(payload.model_dump())

    except (UtteranceOrderError, AnalysisConflictError) as error:
        raise HTTPException(
            status_code=409,
            detail= str(error)
        ) from None

    except AnalysisStorageError:
        raise HTTPException(
            status_code=503, detail="분석 기록을 읽을 수 없습니다."
        ) from None

    except (
        LLMClientError,
        LLMResponseError,
        CorrectionValidationError,
    ) as error:
        print("CORRECTION_ERROR", type(error).__name__, flush=True)

        raise HTTPException(
            status_code=502,
            detail="발화 보정 결과를 정상적으로 얻지 못했습니다.",
        ) from None

    return {
        "status": "context_ready",
        "correction": correction.to_dict(),
    }


@app.post(
    "/api/v1/utterances/analyze",
    response_model=CalculationPreviewResponse,
    tags=["발화 통합 분석"],
    summary="발화 보정·AI 분석·누적 계산·저장",
    description=(
        "앱의 마스킹 발화를 받아 보정하고 현재 + 이전 최대 5개 보정 문장을 AI에 전달합니다. "
        "AI 연결 시 실제 보정 호출이 발생합니다. AI 미연결은 보정 호출 전 503을 반환합니다. "
        "통화 내 utterance_id는 1부터 연속으로 전송합니다. "
        "경고 구현체 연결 시 warning·evidence를 포함하고 미연결 시 두 필드는 null입니다."
    ),
    responses={
        409: {"description": "발화 중복·순서 충돌 또는 이전 실패 복구 필요"},
        502: {"description": "발화 보정 실패"},
        503: {"description": "AI 미연결 또는 저장소 오류"},
    },
)
def receive_and_analyze_utterance(
    payload: UtteranceRequest,
    analyzer: Annotated[RiskAnalyzer, Depends(get_risk_analyzer)],
    warning_manager: Annotated[WarningManager | None, Depends(get_warning_manager)],
):
    try:
        return analyze_utterance(payload, analyzer, warning_manager)
    except ContractError:
        raise HTTPException(status_code=422, detail="발화 마스킹 정보가 올바르지 않습니다.") from None
    except AnalysisConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from None
    except (LLMClientError, LLMResponseError, CorrectionValidationError, InputDataError):
        raise HTTPException(status_code=502, detail="발화 보정 결과를 얻지 못했습니다.") from None
    except AnalysisStorageError:
        raise HTTPException(status_code=503, detail="분석 기록을 읽거나 저장할 수 없습니다.") from None


@app.post(
    "/api/v1/utterances/analyze/retry",
    response_model=CalculationPreviewResponse,
    tags=["발화 통합 분석"],
    summary="저장된 실패 발화를 AI로 재분석",
    description=(
        "통화·발화 ID로 마지막 실패 발화를 선택하고 저장된 보정 문장으로 AI만 재호출합니다. "
        "LLM 보정은 다시 호출하지 않습니다. 이전 실패 시도는 보존합니다."
    ),
    responses={
        404: {"description": "통화 기록 없음"},
        409: {"description": "마지막 실패 발화가 아님"},
        503: {"description": "AI 미연결 또는 저장소 오류"},
    },
)
def reanalyze_utterance(
    payload: UtteranceAnalysisRetryRequest,
    analyzer: Annotated[RiskAnalyzer, Depends(get_risk_analyzer)],
    warning_manager: Annotated[WarningManager | None, Depends(get_warning_manager)],
):
    try:
        return retry_utterance_analysis(
            payload.conversation_id, payload.utterance_id, analyzer, warning_manager,
        )
    except AnalysisNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from None
    except AnalysisConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from None
    except AnalysisStorageError:
        raise HTTPException(status_code=503, detail="분석 기록을 읽거나 저장할 수 없습니다.") from None


@app.post(
    "/api/v1/dev/model-results",
    response_model=CalculationPreviewResponse,
    tags=["개발용 계산 검증"],
    summary="AI 분석 결과로 누적 위험도 계산",
    description=(
        "AI·LLM을 호출하지 않고 전달받은 분석 결과를 저장·계산합니다. "
        "입력 점수는 0~1, 응답 점수는 0~100입니다. "
        "신규 발화(revision=1)만 지원하며 warning·evidence는 경고 구현체 미연결 시 null입니다. "
        "분석 실패는 HTTP 200 및 analysis_status=error, 점수 null로 반환합니다. "
        "통화별 JSON 파일에 입력·응답·계산 설정을 저장하며 단일 worker에서 사용합니다."
    ),
    responses={
        409: {"description": "중복·순서 충돌 또는 이전 분석 실패 복구 필요"},
        503: {"description": "분석 기록 읽기 또는 저장 실패"},
    },
)
def receive_model_result(
    payload: ModelResultRequest,
    warning_manager: Annotated[WarningManager | None, Depends(get_warning_manager)],
):
    try:
        return process_model_result(payload, warning_manager)
    except AnalysisConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from None
    except AnalysisStorageError:
        raise HTTPException(
            status_code=503, detail="분석 기록을 읽거나 저장할 수 없습니다."
        ) from None

@app.post(
    "/api/v1/dev/model-results/retry",
    response_model=CalculationPreviewResponse,
    tags=["개발용 계산 검증"],
    summary="마지막 실패 발화의 재분석 결과 등록",
    description=(
        "해당 통화의 마지막 발화가 error일 때 같은 발화의 재분석 결과를 등록합니다. "
        "발화 ID·sequence·revision·tuned_text는 기존 실패 기록과 같아야 합니다. "
        "AI를 직접 호출하지 않으며 model_version은 새 분석에 실제 사용한 값을 받습니다. "
        "이전 실패 입력·응답은 보존하고 성공 시 후속 발화 처리가 가능해집니다. "
        "재실패 결과도 등록할 수 있으며 이때 후속 차단은 유지됩니다."
    ),
    responses={
        404: {"description": "재시도할 통화 기록 없음"},
        409: {"description": "재시도 대상이 마지막 실패 발화와 일치하지 않음"},
        503: {"description": "분석 기록 읽기 또는 저장 실패"},
    },
)
def retry_analysis(
    payload: ModelResultRequest,
    warning_manager: Annotated[WarningManager | None, Depends(get_warning_manager)],
):
    try:
        return retry_model_result(payload, warning_manager)
    except AnalysisNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from None
    except AnalysisConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from None
    except AnalysisStorageError:
        raise HTTPException(
            status_code=503, detail="분석 기록을 읽거나 저장할 수 없습니다."
        ) from None


@app.get(
    "/api/v1/dev/model-results",
    response_model=CalculationPreviewResponse,
    tags=["개발용 계산 검증"],
    summary="저장된 계산 결과 조회",
    description=(
        "통화 ID로 최신 응답을 조회합니다. utterance_id를 함께 지정하면 "
        "해당 발화의 응답을 반환합니다. AI 호출이나 재계산은 하지 않습니다."
    ),
    responses={
        404: {"description": "저장된 통화 또는 발화 없음"},
        503: {"description": "분석 기록 읽기 실패"},
    },
)
def read_model_result(
    conversation_id: Annotated[str, Query(min_length=1, max_length=120)],
    utterance_id: Annotated[int | None, Query(ge=1)] = None,
):
    try:
        result = get_analysis_result(conversation_id, utterance_id)
    except AnalysisStorageError:
        raise HTTPException(
            status_code=503, detail="분석 기록을 읽을 수 없습니다."
        ) from None
    if result is None:
        raise HTTPException(status_code=404, detail="저장된 분석 결과가 없습니다.")
    return result
