"""근거·경고 이력 인터페이스. 구현체 예: DefaultEvidenceManager."""

from typing import Protocol

from .contracts import (
    CalculationResult,
    ConversationWarningState,
    EvidencePayload,
    ModelRiskResult,
    WarningConfig,
    WarningDecision,
)


class EvidenceManager(Protocol):
    def update(
        self,
        model_result: ModelRiskResult,
        calculation_result: CalculationResult,
        previous_state: ConversationWarningState | None,
        decision: WarningDecision,
        config: WarningConfig,
    ) -> ConversationWarningState:
        """성공한 점수·판단 → 개별 근거, 누적 근거, 이벤트를 갱신한 새 상태.
        첫 진입/재진입은 이벤트 생성, 활성 지속은 갱신, 기준 미만은 종료한다.
        최초 계산과 최고 누적값을 보존하고, 이전 상태를 직접 변경하지 않는다.
        """
        ...

    def build_payload(self, state: ConversationWarningState | None) -> EvidencePayload:
        """저장 근거 → 외부 evidence. 점수는 0~100.
        recent는 발생 순서 최대, highest는 개별 점수 최대(동점은 먼저 발생).
        cumulative_events는 first_cumulative의 최초 기여 발화와 점수로 구성한다.
        근거 없음은 recent/highest=None, cumulative_events=[].
        """
        ...
