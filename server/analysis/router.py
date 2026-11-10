import logging
from functools import partial
from time import perf_counter
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from backend.schemas import UtteranceAnalysisRetryRequest, UtteranceRequest
from backend.services.analysis_service import AnalysisNotFoundError, get_analysis_result
from backend.services.notification_service import NotificationNotFoundError
from backend.services.pipeline_service import analyze_utterance, retry_utterance_analysis
from backend.services.warning_service import WarningIntegrationError
from backend.stores.analysis_file_store import AnalysisStorageError
from backend.stores.analysis_store import AnalysisConflictError
from models.llm_correction import ContractError
from server.analysis.context_service import prepare_utterance
from server.analysis.risk_display import AnalysisWithDisplay, add_risk_display
from server.security.access import authenticated_device, require_conversation_owner
from server.security import limits


router = APIRouter(prefix="/api/v1/utterances", tags=["발화 분석"])


class MaskedUtteranceRequest(UtteranceRequest):
    # 개인정보 미검출(false)과 마스킹 미실행을 구분한다.
    masking_status: Literal["succeeded"]


def get_analyzer(request: Request):
    analyzer = getattr(request.app.state, "risk_analyzer", None)
    if analyzer is None:
        raise HTTPException(503, "위험 탐지 AI가 연결되지 않았습니다.")
    return analyzer


def run_analysis(operation, *args, **kwargs):
    """분석·조회·종료 진입점의 서비스 오류를 같은 HTTP 계약으로 변환한다."""
    try:
        return operation(*args, **kwargs)
    except ContractError:
        raise HTTPException(422, "발화 마스킹 정보가 올바르지 않습니다.") from None
    except (AnalysisNotFoundError, NotificationNotFoundError):
        raise HTTPException(404, "저장된 통화 또는 결과를 찾을 수 없습니다.") from None
    except AnalysisConflictError as error:
        raise HTTPException(409, str(error)) from None
    except (AnalysisStorageError, WarningIntegrationError):
        raise HTTPException(503, "분석 기록 저장 또는 경고 처리에 실패했습니다.") from None


@router.post("/analyze", response_model=AnalysisWithDisplay)
def analyze(
    payload: MaskedUtteranceRequest, request: Request, response: Response,
    owner: Annotated[str, Depends(authenticated_device)],
    analyzer: Annotated[object, Depends(get_analyzer)],
):
    require_conversation_owner(owner, payload.conversation_id)
    if not limits.analysis_requests.allow(owner):
        raise HTTPException(429, "분석 요청이 너무 많습니다.", headers={"Retry-After": "60"})
    # 상속된 요청 필드는 이미 검증했으므로 기존 계약으로 변환만 한다.
    original = UtteranceRequest.model_construct(**payload.model_dump(exclude={"masking_status"}))
    timings: dict[str, float] = {}
    started = perf_counter()
    try:
        result = run_analysis(
            analyze_utterance, original, analyzer, request.app.state.warning_manager,
            allow_correction_fallback=True,
            prepare_utterance=partial(prepare_utterance, client=request.app.state.llm_client),
            timings=timings,
        )
    finally:
        timings["total"] = (perf_counter() - started) * 1000
        # 시간만 기록한다. 발화·통화 ID·키·외부 응답은 로그에 넣지 않는다.
        timing_header = ", ".join(f"{name};dur={ms:.2f}" for name, ms in timings.items())
        logging.getLogger("uvicorn.error").info("ANALYSIS_TIMING %s", timing_header)
    response.headers["Server-Timing"] = timing_header
    return add_risk_display(result)


@router.post("/analyze/retry", response_model=AnalysisWithDisplay)
def retry(
    payload: UtteranceAnalysisRetryRequest, request: Request,
    owner: Annotated[str, Depends(authenticated_device)],
    analyzer: Annotated[object, Depends(get_analyzer)],
):
    require_conversation_owner(owner, payload.conversation_id)
    if not limits.analysis_requests.allow(owner):
        raise HTTPException(429, "분석 요청이 너무 많습니다.", headers={"Retry-After": "60"})
    return add_risk_display(run_analysis(
        retry_utterance_analysis, payload.conversation_id, payload.utterance_id,
        analyzer, request.app.state.warning_manager,
    ))


@router.get("/results", response_model=AnalysisWithDisplay)
def read_result(
    conversation_id: Annotated[str, Query(min_length=1, max_length=120, pattern=r"\S")],
    response: Response,
    owner: Annotated[str, Depends(authenticated_device)],
    utterance_id: Annotated[int | None, Query(ge=1)] = None,
):
    """AI 재호출 없이 저장된 최신 또는 특정 발화 결과를 반환한다."""
    require_conversation_owner(owner, conversation_id)
    response.headers["Cache-Control"] = "no-store"
    result = run_analysis(get_analysis_result, conversation_id, utterance_id)
    if result is None:
        raise HTTPException(404, "저장된 분석 결과를 찾을 수 없습니다.")
    return add_risk_display(result)
