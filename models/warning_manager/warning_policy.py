"""경고 판단 인터페이스와 실제 구현."""

from typing import Protocol

from .contracts import (
    CalculationResult,
    ConversationWarningState,
    WarningConfig,
    WarningDecision,
)


class WarningPolicy(Protocol):
    def evaluate(
        self,
        calculation_result: CalculationResult,
        previous_state: ConversationWarningState | None,
        config: WarningConfig,
        ) -> WarningDecision:
            """경고 상태와 사유를 판단하는 함수의 형식."""
            ...

class DefaultWarningPolicy:
    """검증된 서버 계산 결과로 경고 상태와 사유를 판단한다."""

    def evaluate(
        self,
        calculation_result: CalculationResult,
        previous_state: ConversationWarningState | None,
        config: WarningConfig,
    ) -> WarningDecision:
        threshold = config.warning_threshold

        if calculation_result.cumulative_score >= threshold:
            single_triggered = (
                calculation_result.window_max_score >= threshold
            )
            cumulative_triggered = (
                calculation_result.accumulated_score >= threshold
            )

            if single_triggered and cumulative_triggered:
                return WarningDecision(
                    status="active",
                    reason="both",
                )

            if single_triggered:
                return WarningDecision(
                    status="active",
                    reason="single_utterance",
                )

            if cumulative_triggered:
                return WarningDecision(
                    status="active",
                    reason="cumulative",
                )

            raise ValueError(
                "경고 기준 이상이지만 경고 사유에 해당하는 점수가 없습니다."
            )

        if previous_state is not None and previous_state.events:
            latest_event = previous_state.events[-1]

            return WarningDecision(
                status="previous_warning",
                reason=latest_event.reason,
            )

        return WarningDecision(
            status="none",
            reason=None,
        )