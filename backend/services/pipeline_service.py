"""마스킹 발화 → 보정 → AI → 누적 계산·저장 연결."""

import logging
from collections.abc import Callable
from time import perf_counter

from backend.schemas import CalculationPreviewResponse, ContextJudgmentResult, ModelResultRequest, UtteranceRequest
from backend.services import analysis_service
from backend.services.ai_service import RiskAnalyzer, RiskModelInput, RiskModelScores
from backend.services.utterance_service import get_correction_engine, validate_utterance
from backend.stores.analysis_store import AnalysisConflictError
from models.context_manager import InputDataError, merge_utterance
from models.llm_correction import CorrectionValidationError, LLMClientError, LLMResponseError, MaskedTranscript
from models.warning_manager.warning_manager import WarningManager


logger = logging.getLogger(__name__)


def _run_ai(
    analyzer: RiskAnalyzer,
    *,
    conversation_id: str,
    utterance_id: int,
    sequence: int,
    tuned_text: str,
    history_texts: tuple[str, ...],
) -> ModelResultRequest:
    metadata = {
        "conversation_id": conversation_id,
        "utterance_id": utterance_id,
        "revision": 1,
        "sequence": sequence,
        "tuned_text": tuned_text,
        "model_version": analyzer.model_version,
    }
    try:
        result = analyzer.analyze(RiskModelInput(tuned_text, history_texts))
        # model_construct 등으로 생성된 객체도 값 범위를 다시 검사한다.
        if not isinstance(result, RiskModelScores):
            raise ValueError("RiskModelScores 결과가 필요합니다.")
        scores = RiskModelScores.model_validate(result.model_dump())
        return ModelResultRequest(
            **metadata, analysis_status="ok", **scores.model_dump()
        )
    except Exception as error:
        # AI 호출 경계의 실패만 기록한다. 문장·키·예외 원문은 남기지 않는다.
        logger.warning("RISK_ANALYSIS_ERROR %s", type(error).__name__)
        return ModelResultRequest(
            **metadata, analysis_status="error", is_phishing_score=None,
            type_scores=None, detected_types=None,
        )


def analyze_utterance(
    payload: UtteranceRequest, analyzer: RiskAnalyzer,
    warning_manager: WarningManager | None = None,
    *, allow_correction_fallback: bool = False,
    context_judge: analysis_service.ContextJudge | None = None,
    timings: dict[str, float] | None = None,
    prepare_utterance: Callable[[MaskedTranscript, list[ModelResultRequest]], tuple[str, ContextJudgmentResult]] | None = None,
) -> CalculationPreviewResponse:
    timings = timings if timings is not None else {}
    started = perf_counter()
    transcript = validate_utterance(payload.model_dump())
    timings["validation"] = (perf_counter() - started) * 1000

    # 같은 통화의 기록 조회부터 보정·AI 분석·저장까지 보호한다.
    started = perf_counter()
    with analysis_service.conversation_locks.hold(transcript.conversation_id):
        timings["lock_wait"] = (perf_counter() - started) * 1000
        started = perf_counter()
        snapshot = analysis_service.analysis_store.load(
            transcript.conversation_id
        )
        analysis_service.ensure_conversation_active(snapshot)
        config = analysis_service.prepare_warning_session(snapshot, warning_manager)
        records = snapshot.records if snapshot is not None else []
        
        if records and records[-1].model_result.analysis_status == "error":
            raise analysis_service.AnalysisPendingError(
                "이전 분석 실패를 복구한 뒤 다음 발화를 보내야 합니다."
            )
        expected_id = len(records) + 1
        if transcript.utterance_id != expected_id or any(
            item.model_result.utterance_id == transcript.utterance_id for item in records
        ):
            raise AnalysisConflictError(f"다음 utterance_id는 {expected_id}여야 합니다.")

        timings["load_prepare"] = (perf_counter() - started) * 1000
        correction_status = None
        started = perf_counter()
        context_result = None
        if prepare_utterance is not None:
            tuned_text, context_result = prepare_utterance(
                transcript, [item.model_result for item in records],
            )
            correction_status = "ok" if context_result.status == "ok" else "fallback"
            timings["llm_preparation"] = (perf_counter() - started) * 1000
        else:
            try:
                correction = get_correction_engine().correct(transcript)
                utterance = merge_utterance(transcript.to_dict(), correction.to_dict())
                if len(utterance.tuned_text) > 10_000:
                    raise CorrectionValidationError("보정 문장이 서버의 길이 제한을 초과했습니다.")
                tuned_text = utterance.tuned_text
                if allow_correction_fallback:
                    correction_status = "ok"
            except (LLMClientError, LLMResponseError, CorrectionValidationError, InputDataError):
                if not allow_correction_fallback:
                    raise
                # 입력 검증은 위에서 끝났다. 실패한 보정 출력은 사용하지 않는다.
                tuned_text = transcript.masked_text
                correction_status = "fallback"
            finally:
                timings["correction"] = (perf_counter() - started) * 1000
        started = perf_counter()
        model_result = _run_ai(
            analyzer,
            conversation_id=transcript.conversation_id,
            utterance_id=transcript.utterance_id,
            sequence=expected_id,
            tuned_text=tuned_text,
            history_texts=tuple(item.model_result.tuned_text for item in records[-5:]),
        )
        timings["ai_inference"] = (perf_counter() - started) * 1000
        return analysis_service._process_model_result_locked(
            model_result, snapshot, warning_manager, config,
            correction_status=correction_status,
            context_judge=context_judge,
            timings=timings,
            context_result=context_result,
        )

def retry_utterance_analysis(
    conversation_id: str, utterance_id: int, analyzer: RiskAnalyzer,
    warning_manager: WarningManager | None = None,
    *, context_judge: analysis_service.ContextJudge | None = None,
) -> CalculationPreviewResponse:
    """보정은 재호출하지 않고 AI 재분석 후 선택적 문맥 판단까지 저장한다."""

    with analysis_service.conversation_locks.hold(conversation_id):
        snapshot = analysis_service.analysis_store.load(conversation_id)
        if snapshot is None:
            raise analysis_service.AnalysisNotFoundError(
                "재시도할 통화 기록이 없습니다."
            )
        analysis_service.ensure_conversation_active(snapshot)
        config = analysis_service.prepare_warning_session(snapshot, warning_manager)
        
        failed = snapshot.records[-1].model_result
        if failed.utterance_id != utterance_id or failed.analysis_status != "error":
            raise AnalysisConflictError("해당 통화의 마지막 실패 발화만 재시도할 수 있습니다.")

        model_result = _run_ai(
            analyzer,
            conversation_id=conversation_id,
            utterance_id=utterance_id,
            sequence=failed.sequence,
            tuned_text=failed.tuned_text,
            history_texts=tuple(
                item.model_result.tuned_text for item in snapshot.records[:-1][-5:]
            ),
        )
        return analysis_service._retry_model_result_locked(
            model_result, snapshot, warning_manager, config,
            context_judge=context_judge,
        )
