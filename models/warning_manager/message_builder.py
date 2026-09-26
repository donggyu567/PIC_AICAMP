"""경고 상태와 분석 결과에 맞는 안내 문구를 만든다."""

from typing import Protocol

from .contracts import (
    CalculationResult,
    EvidencePayload,
    ModelRiskResult,
    WarningDecision,
)


class MessageBuilder(Protocol):
    def build(
        self,
        model_result: ModelRiskResult,
        calculation_result: CalculationResult | None,
        decision: WarningDecision,
        evidence: EvidencePayload,
        *,
        conversation_ended: bool = False,
    ) -> str:
        """경고 상태와 근거에 맞는 안내 문구를 반환한다."""
        ...


def build_analysis_failure_message(
    *,
    has_previous_state: bool,
    decision: WarningDecision,
    evidence: EvidencePayload,
    conversation_ended: bool = False,
) -> str:
    """이전 상태 유무에 따라 분석 실패 문구를 만든다."""
    if not has_previous_state:
        if conversation_ended:
            return (
                "이번 통화의 발화를 분석하지 못해 "
                "위험도를 판단할 수 없습니다."
            )
        return "이번 발화를 분석하지 못해 위험도를 판단할 수 없습니다."

    if conversation_ended:
        lead = "이번 통화의 발화 분석 결과를 갱신하지 못했습니다."
    else:
        lead = "이번 발화의 분석 결과를 갱신하지 못했습니다."

    has_evidence = (
        evidence["recent"] is not None
        or evidence["highest"] is not None
        or bool(evidence["cumulative_events"])
    )

    if decision.status != "none" and has_evidence:
        previous = "이전 경고와 근거"
    elif decision.status != "none":
        previous = "이전 경고"
    elif has_evidence:
        previous = "이전 근거"
    else:
        previous = "이전 분석 결과"

    return f"{lead} {previous}를 표시합니다."


class TemplateMessageBuilder:
    """추가 AI 호출 없이 정해진 문구 중 하나를 선택한다."""

    def build(
        self,
        model_result: ModelRiskResult,
        calculation_result: CalculationResult | None,
        decision: WarningDecision,
        evidence: EvidencePayload,
        *,
        conversation_ended: bool = False,
    ) -> str:
        if model_result.analysis_status == "error":
            if calculation_result is not None:
                raise ValueError("분석 실패에는 계산 결과가 없어야 합니다.")

            return build_analysis_failure_message(
                has_previous_state=True,
                decision=decision,
                evidence=evidence,
                conversation_ended=conversation_ended,
            )

        if model_result.analysis_status != "ok":
            raise ValueError("알 수 없는 분석 상태입니다.")

        if calculation_result is None:
            raise ValueError("분석 성공에는 계산 결과가 필요합니다.")

        if decision.status == "none":
            if decision.reason is not None:
                raise ValueError("경고가 없으면 사유도 없어야 합니다.")

            if conversation_ended:
                return (
                    "이번 통화에서 경고 기준에 해당하는 위험 신호는 "
                    "감지되지 않았습니다."
                )
            return (
                "현재까지 경고 기준에 해당하는 위험 신호가 "
                "감지되지 않았습니다."
            )

        if decision.status == "previous_warning":
            if decision.reason is None:
                raise ValueError("과거 경고에는 저장된 사유가 필요합니다.")

            has_evidence = (
                evidence["recent"] is not None
                or evidence["highest"] is not None
                or bool(evidence["cumulative_events"])
            )
            if not has_evidence:
                return "이전에 경고 기준에 도달한 기록을 확인해 주세요."

            if conversation_ended:
                return "이번 통화에서 감지된 위험 발화를 확인해 주세요."
            return "통화 중 감지된 위험 발화를 확인해 주세요."

        if decision.status == "active":
            if decision.reason == "single_utterance":
                if conversation_ended:
                    return "이번 통화에서 위험도가 높은 발화가 감지되었습니다."
                return "최근 대화에서 위험도가 높은 발화가 감지되었습니다."

            if decision.reason == "cumulative":
                if conversation_ended:
                    return (
                        "이번 통화의 누적 위험도가 "
                        "경고 기준에 도달했습니다."
                    )
                return "최근 대화의 누적 위험도가 경고 기준에 도달했습니다."

            if decision.reason == "both":
                if conversation_ended:
                    return (
                        "이번 통화에서 고위험 발화와 누적 위험도가 "
                        "모두 경고 기준에 도달했습니다."
                    )
                return (
                    "고위험 발화와 누적 위험도가 모두 "
                    "경고 기준에 도달했습니다."
                )

            raise ValueError("활성 경고의 사유가 올바르지 않습니다.")

        raise ValueError("알 수 없는 경고 상태입니다.")