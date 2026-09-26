"""분석 결과와 계산 결과를 외부 응답 형식으로 변환한다."""

from backend.schemas import CalculationDetails, CalculationPreviewResponse
from models.warning_manager.contracts import CalculationResult, ModelRiskResult, WarningResult


def build_analysis_response(
    current: ModelRiskResult,
    calculation: CalculationResult | None,
    warning_result: WarningResult | None = None,
) -> CalculationPreviewResponse:
    details = None
    if calculation is not None:
        details = CalculationDetails(
            window_max_score=calculation.window_max_score,
            accumulated_score=calculation.accumulated_score,
            window_utterance_ids=[
                item.utterance.utterance_id
                for item in calculation.window_utterances
            ],
            window_size=calculation.window_size,
            rho=calculation.rho,
            b=calculation.b,
            policy_version=calculation.policy_version,
        )

    return CalculationPreviewResponse(
        conversation_id=current.conversation_id,
        utterance_id=current.utterance_id,
        revision=current.revision,
        sequence=current.sequence,
        analysis_status=current.analysis_status,
        current_text=current.tuned_text,
        current_risk_score=(
            100.0 * current.is_phishing_score
            if current.is_phishing_score is not None else None
        ),
        cumulative_risk_score=(
            calculation.cumulative_score if calculation is not None else None
        ),
        type_scores=(
            {name: 100.0 * score for name, score in current.type_scores.items()}
            if current.type_scores is not None else None
        ),
        detected_types=(
            list(current.detected_types)
            if current.detected_types is not None else None
        ),
        calculation=details,
        warning=warning_result["warning"] if warning_result is not None else None,
        evidence=warning_result["evidence"] if warning_result is not None else None,
    )
