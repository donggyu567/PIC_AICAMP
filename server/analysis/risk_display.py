"""앱 표시용 단계. 기존 위험 계산과 경고 이력은 변경하지 않는다."""

from typing import Literal

from pydantic import BaseModel

from backend.schemas import CalculationPreviewResponse, ConversationEndResponse


class RiskDisplay(BaseModel):
    level: Literal["normal", "caution", "danger", "unknown"]
    context_attention: bool | None


class AnalysisWithDisplay(CalculationPreviewResponse):
    display: RiskDisplay


class ConversationEndWithDisplay(ConversationEndResponse):
    last_analysis: AnalysisWithDisplay | None = None


def add_risk_display(result: CalculationPreviewResponse) -> AnalysisWithDisplay:
    score = result.cumulative_risk_score
    if result.analysis_status != "ok" or score is None:
        level = "unknown"
    elif score >= 70:
        level = "danger"
    elif score >= 50:
        level = "caution"
    else:
        level = "normal"

    context = result.context_judgment
    assessment = context.result.assessment if context.status == "ok" and context.result else None
    attention = True if assessment == "suspicious" else False if assessment == "no_clear_risk" else None
    return AnalysisWithDisplay(**result.model_dump(), display=RiskDisplay(level=level, context_attention=attention))


def add_final_risk_display(result: ConversationEndResponse) -> ConversationEndWithDisplay:
    final = result.last_analysis
    return ConversationEndWithDisplay(
        **result.model_dump(exclude={"last_analysis"}),
        last_analysis=add_risk_display(final) if final is not None else None,
    )
