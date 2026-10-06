"""마스킹 발화 → 보정 → AI → 누적 계산·저장 연결."""

import logging

from backend.schemas import CalculationPreviewResponse, ModelResultRequest, UtteranceRequest
from backend.services import analysis_service
from backend.services.ai_service import RiskAnalyzer, RiskModelInput, RiskModelScores
from backend.services.utterance_service import get_correction_engine, validate_utterance
from backend.stores.analysis_store import AnalysisConflictError
from models.context_manager import merge_utterance
from models.llm_correction import CorrectionValidationError
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
) -> CalculationPreviewResponse:
    transcript = validate_utterance(payload.model_dump())

    # 기록 조회부터 보정·AI 분석·저장까지 같은 잠금으로 보호한다.
    with analysis_service.analysis_lock:
        snapshot = analysis_service.analysis_store.load(
            transcript.conversation_id
        )
        analysis_service.ensure_conversation_active(snapshot)
        analysis_service.prepare_warning_session(snapshot, warning_manager)
        records = snapshot.records if snapshot is not None else []
        
        if any(item.model_result.analysis_status == "error" for item in records):
            raise analysis_service.AnalysisPendingError(
                "이전 분석 실패를 복구한 뒤 다음 발화를 보내야 합니다."
            )
        expected_id = len(records) + 1
        if transcript.utterance_id != expected_id or any(
            item.model_result.utterance_id == transcript.utterance_id for item in records
        ):
            raise AnalysisConflictError(f"다음 utterance_id는 {expected_id}여야 합니다.")

        correction = get_correction_engine().correct(transcript)
        utterance = merge_utterance(transcript.to_dict(), correction.to_dict())
        if len(utterance.tuned_text) > 10_000:
            raise CorrectionValidationError("보정 문장이 서버의 길이 제한을 초과했습니다.")

        model_result = _run_ai(
            analyzer,
            conversation_id=transcript.conversation_id,
            utterance_id=transcript.utterance_id,
            sequence=expected_id,
            tuned_text=utterance.tuned_text,
            history_texts=tuple(item.model_result.tuned_text for item in records[-5:]),
        )
        return analysis_service._process_model_result_locked(
            model_result, snapshot, warning_manager
        )

def retry_utterance_analysis(
    conversation_id: str, utterance_id: int, analyzer: RiskAnalyzer,
    warning_manager: WarningManager | None = None,
) -> CalculationPreviewResponse:
    """저장된 보정 문장·이전 문맥으로 AI만 재호출한다."""

    with analysis_service.analysis_lock:
        snapshot = analysis_service.analysis_store.load(conversation_id)
        if snapshot is None:
            raise analysis_service.AnalysisNotFoundError(
                "재시도할 통화 기록이 없습니다."
            )
        analysis_service.ensure_conversation_active(snapshot)
        analysis_service.prepare_warning_session(snapshot, warning_manager)
        
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
            model_result, snapshot, warning_manager,
        )
