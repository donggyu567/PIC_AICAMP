"""템플릿 문구 인터페이스. 구현체 예: TemplateMessageBuilder."""

from typing import Protocol

from .contracts import CalculationResult, EvidencePayload, ModelRiskResult, WarningDecision


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
        """점수·경고·실제 근거로 문구를 구성한다. 실패 시 갱신 실패를 표시한다.
        과거 유형을 현재 유형으로 표시하지 않으며 LLM 호출·상태 변경은 하지 않는다.
        """
        ...
