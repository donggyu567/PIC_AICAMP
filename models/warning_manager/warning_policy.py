"""경고 판단 인터페이스. 구현체 예: DefaultWarningPolicy."""

from typing import Protocol

from .contracts import CalculationResult, ConversationWarningState, WarningConfig, WarningDecision


class WarningPolicy(Protocol):
    def evaluate(
        self,
        calculation_result: CalculationResult,
        previous_state: ConversationWarningState | None,
        config: WarningConfig,
    ) -> WarningDecision:
        """누적값으로 상태, M/A 점수의 각각 기준 충족 여부로 사유를 판단한다.
        previous_warning의 사유는 최신 유효 이벤트에서 가져온다.
        비교는 반올림 전에 수행한다. 누적식을 재실행하거나 상태를 변경하지 않는다.
        """
        ...
