"""서버 진입 인터페이스. 실제 통합 구현은 이 계약에 맞춰 별도로 작성한다."""

from typing import Protocol

from .contracts import (
    CalculationResult,
    ConversationWarningState,
    ModelRiskResult,
    WarningConfig,
    WarningUpdate,
)


class WarningManager(Protocol):
    def update_warning(
        self,
        model_result: ModelRiskResult,
        calculation_result: CalculationResult | None,
        previous_state: ConversationWarningState | None,
        config: WarningConfig,
        *,
        is_replay: bool = False,
        conversation_ended: bool = False,
    ) -> WarningUpdate:
        """검증 → 정책 판단 → 상태 갱신 → evidence·문구 생성 → 결과 반환.
        error 입력은 계산 결과가 None이며, 기존 상태를 유지하고 실패 문구만 구성한다.
        새 실시간 이벤트만 notify_event_id를 반환한다. 재생/종료/실패는 None.
        잘못된 입력은 ValueError, 내부 실패는 예외로 전달하며 입력을 변경하지 않는다.
        중복·순서·정정 재생·DB 저장은 서버 책임이다.
        """
        ...
