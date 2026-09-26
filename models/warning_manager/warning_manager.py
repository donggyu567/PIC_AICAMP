"""경고 판단, 근거 관리, 안내 문구 생성을 연결한다."""

import math
from typing import Protocol, get_args

from .contracts import (
    CalculationResult,
    ConversationWarningState,
    EvidencePayload,
    ModelRiskResult,
    RiskType,
    WarningConfig,
    WarningDecision,
    WarningEvent,
    WarningResult,
    WarningUpdate,
    WindowUtterance,
)
from .evidence_manager import DefaultEvidenceManager
from .message_builder import (
    TemplateMessageBuilder,
    build_analysis_failure_message,
)
from .warning_policy import DefaultWarningPolicy


_RISK_TYPES = frozenset(get_args(RiskType))


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
        """입력 검증부터 경고 결과 반환까지 처리한다."""
        ...


def _require_text(value: object, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name}은 비어 있지 않은 문자열이어야 합니다.")


def _require_integer(value: object, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name}은 0 이상의 정수여야 합니다.")


def _require_number(
    value: object,
    name: str,
    minimum: float | None = None,
    maximum: float | None = None,
) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
    ):
        raise ValueError(f"{name}은 유한한 숫자여야 합니다.")

    if minimum is not None and value < minimum:
        raise ValueError(f"{name}이 허용 범위보다 작습니다.")

    if maximum is not None and value > maximum:
        raise ValueError(f"{name}이 허용 범위보다 큽니다.")


def _validate_model_result(result: ModelRiskResult) -> None:
    if not isinstance(result, ModelRiskResult):
        raise ValueError("model_result의 형식이 올바르지 않습니다.")

    _require_text(result.conversation_id, "conversation_id")
    _require_text(result.tuned_text, "tuned_text")
    _require_text(result.model_version, "model_version")
    _require_integer(result.utterance_id, "utterance_id")
    _require_integer(result.revision, "revision")
    _require_integer(result.sequence, "sequence")

    if result.analysis_status not in ("ok", "error"):
        raise ValueError("analysis_status는 ok 또는 error여야 합니다.")

    if result.analysis_status == "error":
        if (
            result.is_phishing_score is not None
            or result.type_scores is not None
            or result.detected_types is not None
        ):
            raise ValueError("분석 실패 시 점수와 유형은 모두 None이어야 합니다.")
        return

    _require_number(
        result.is_phishing_score,
        "is_phishing_score",
        0.0,
        1.0,
    )

    if (
        not isinstance(result.type_scores, dict)
        or set(result.type_scores) != _RISK_TYPES
    ):
        raise ValueError("type_scores에는 8개 유형이 모두 있어야 합니다.")

    for risk_type, score in result.type_scores.items():
        _require_number(score, f"type_scores[{risk_type}]", 0.0, 1.0)

    if (
        not isinstance(result.detected_types, tuple)
        or any(
            not isinstance(risk_type, str)
            or risk_type not in _RISK_TYPES
            for risk_type in result.detected_types
        )
    ):
        raise ValueError("detected_types의 형식이 올바르지 않습니다.")


def _validate_config(config: WarningConfig) -> None:
    if not isinstance(config, WarningConfig):
        raise ValueError("config의 형식이 올바르지 않습니다.")

    _require_number(
        config.evidence_threshold,
        "evidence_threshold",
        0.0,
        100.0,
    )
    _require_number(
        config.warning_threshold,
        "warning_threshold",
        0.0,
        100.0,
    )
    _require_integer(
        config.representative_evidence_count,
        "representative_evidence_count",
    )
    _require_text(config.warning_policy_version, "warning_policy_version")


def _validate_previous_state(
    previous_state: ConversationWarningState | None,
    conversation_id: str,
    config: WarningConfig,
) -> None:
    if previous_state is None:
        return

    if not isinstance(previous_state, ConversationWarningState):
        raise ValueError("previous_state의 형식이 올바르지 않습니다.")

    if previous_state.conversation_id != conversation_id:
        raise ValueError("이전 상태가 다른 통화에 속합니다.")

    if previous_state.config != config:
        raise ValueError("같은 통화의 경고 설정이 변경되었습니다.")

    if previous_state.status not in (
        "none",
        "active",
        "previous_warning",
    ):
        raise ValueError("이전 경고 상태가 올바르지 않습니다.")

    if previous_state.cumulative_score is not None:
        _require_number(
            previous_state.cumulative_score,
            "previous_state.cumulative_score",
            0.0,
            100.0,
        )

    if (
        not isinstance(previous_state.individual_evidence, tuple)
        or not isinstance(previous_state.events, tuple)
    ):
        raise ValueError("이전 근거와 이벤트는 튜플이어야 합니다.")

    if previous_state.status == "none":
        if previous_state.events:
            raise ValueError("경고 이력이 있으면 상태가 none일 수 없습니다.")
        return

    if not previous_state.events:
        raise ValueError("과거 경고 상태에는 이벤트가 필요합니다.")

    latest_event = previous_state.events[-1]
    if not isinstance(latest_event, WarningEvent):
        raise ValueError("마지막 경고 이벤트의 형식이 올바르지 않습니다.")

    if latest_event.reason not in (
        "single_utterance",
        "cumulative",
        "both",
    ):
        raise ValueError("마지막 경고 이벤트의 사유가 올바르지 않습니다.")

    if (
        previous_state.status == "active"
        and latest_event.closed_sequence is not None
    ):
        raise ValueError("활성 경고의 마지막 이벤트가 종료되어 있습니다.")

    if (
        previous_state.status == "previous_warning"
        and latest_event.closed_sequence is None
    ):
        raise ValueError("과거 경고의 마지막 이벤트가 열려 있습니다.")


def _validate_calculation(
    calculation_result: CalculationResult,
    model_result: ModelRiskResult,
    config: WarningConfig,
) -> None:
    if not isinstance(calculation_result, CalculationResult):
        raise ValueError("calculation_result의 형식이 올바르지 않습니다.")

    model_key = (
        model_result.conversation_id,
        model_result.utterance_id,
        model_result.revision,
    )
    calculation_key = (
        calculation_result.conversation_id,
        calculation_result.utterance_id,
        calculation_result.revision,
    )
    if calculation_key != model_key:
        raise ValueError("분석 결과와 계산 결과의 식별자가 다릅니다.")

    _require_number(
        calculation_result.cumulative_score,
        "cumulative_score",
        0.0,
        100.0,
    )
    _require_number(
        calculation_result.window_max_score,
        "window_max_score",
        0.0,
        100.0,
    )
    _require_number(
        calculation_result.accumulated_score,
        "accumulated_score",
        0.0,
        100.0,
    )

    expected_score = max(
        calculation_result.window_max_score,
        calculation_result.accumulated_score,
    )
    if not math.isclose(
        calculation_result.cumulative_score,
        expected_score,
        rel_tol=1e-12,
        abs_tol=1e-9,
    ):
        raise ValueError("최종 누적 위험도와 원인 점수가 일치하지 않습니다.")

    if (
        calculation_result.cumulative_score >= config.warning_threshold
    ) != (
        expected_score >= config.warning_threshold
    ):
        raise ValueError("경고 기준을 기준으로 계산 점수가 일치하지 않습니다.")

    _require_text(calculation_result.policy_version, "policy_version")
    _require_integer(calculation_result.window_size, "window_size")
    if calculation_result.window_size == 0:
        raise ValueError("window_size는 1 이상이어야 합니다.")

    _require_number(calculation_result.rho, "rho")
    _require_number(calculation_result.b, "b")

    window = calculation_result.window_utterances
    if (
        not isinstance(window, tuple)
        or not window
        or len(window) > calculation_result.window_size
    ):
        raise ValueError("계산 창의 크기가 올바르지 않습니다.")

    previous_sequence: int | None = None
    for item in window:
        if not isinstance(item, WindowUtterance):
            raise ValueError("계산 창에 잘못된 발화 항목이 있습니다.")

        _validate_model_result(item.utterance)
        if item.utterance.analysis_status != "ok":
            raise ValueError("계산 창에는 분석에 성공한 발화만 들어갑니다.")

        if item.utterance.conversation_id != model_result.conversation_id:
            raise ValueError("계산 창에 다른 통화의 발화가 들어 있습니다.")

        if (
            previous_sequence is not None
            and item.utterance.sequence <= previous_sequence
        ):
            raise ValueError("계산 창의 발화 순서가 올바르지 않습니다.")

        _require_number(item.weight, "weight", 0.0)
        _require_number(item.effective_risk, "effective_risk", 0.0, 1.0)
        _require_number(item.contribution, "contribution", 0.0, 1.0)

        if not math.isclose(
            item.contribution,
            item.weight * item.effective_risk,
            rel_tol=1e-9,
            abs_tol=1e-12,
        ):
            raise ValueError("발화 기여도와 가중치 계산이 일치하지 않습니다.")

        previous_sequence = item.utterance.sequence

    if window[-1].utterance != model_result:
        raise ValueError("계산 창의 마지막 항목이 현재 발화와 다릅니다.")


def _decision_for_failure(
    previous_state: ConversationWarningState | None,
) -> WarningDecision:
    if previous_state is None or previous_state.status == "none":
        return WarningDecision(status="none", reason=None)

    return WarningDecision(
        status=previous_state.status,
        reason=previous_state.events[-1].reason,
    )


def _build_result(
    decision: WarningDecision,
    evidence: EvidencePayload,
    message: str,
) -> WarningResult:
    return {
        "warning": {
            "status": decision.status,
            "reason": decision.reason,
            "message": message,
        },
        "evidence": evidence,
    }


class DefaultWarningManager:
    """검증된 입력으로 경고 상태와 앱 표시 결과를 만든다."""

    def __init__(self) -> None:
        self._policy = DefaultWarningPolicy()
        self._evidence_manager = DefaultEvidenceManager()
        self._message_builder = TemplateMessageBuilder()

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
        _validate_model_result(model_result)
        _validate_config(config)
        _validate_previous_state(
            previous_state,
            model_result.conversation_id,
            config,
        )

        if not isinstance(is_replay, bool):
            raise ValueError("is_replay는 불리언이어야 합니다.")
        if not isinstance(conversation_ended, bool):
            raise ValueError("conversation_ended는 불리언이어야 합니다.")

        if model_result.analysis_status == "error":
            if calculation_result is not None:
                raise ValueError("분석 실패에는 계산 결과가 없어야 합니다.")

            decision = _decision_for_failure(previous_state)
            evidence = self._evidence_manager.build_payload(previous_state)

            if previous_state is None:
                message = build_analysis_failure_message(
                    has_previous_state=False,
                    decision=decision,
                    evidence=evidence,
                    conversation_ended=conversation_ended,
                )
            else:
                message = self._message_builder.build(
                    model_result,
                    None,
                    decision,
                    evidence,
                    conversation_ended=conversation_ended,
                )

            return WarningUpdate(
                result=_build_result(decision, evidence, message),
                state=previous_state,
                notify_event_id=None,
            )

        if calculation_result is None:
            raise ValueError("분석 성공에는 계산 결과가 필요합니다.")

        _validate_calculation(calculation_result, model_result, config)

        decision = self._policy.evaluate(
            calculation_result,
            previous_state,
            config,
        )
        state = self._evidence_manager.update(
            model_result,
            calculation_result,
            previous_state,
            decision,
            config,
        )
        evidence = self._evidence_manager.build_payload(state)
        message = self._message_builder.build(
            model_result,
            calculation_result,
            decision,
            evidence,
            conversation_ended=conversation_ended,
        )

        notify_event_id = None
        new_event = (
            decision.status == "active"
            and (
                previous_state is None
                or previous_state.status != "active"
            )
        )
        if new_event:
            previous_count = (
                len(previous_state.events)
                if previous_state is not None
                else 0
            )
            if (
                len(state.events) != previous_count + 1
                or state.events[-1].closed_sequence is not None
            ):
                raise ValueError("새 경고 이벤트가 생성되지 않았습니다.")

            if not is_replay and not conversation_ended:
                notify_event_id = state.events[-1].event_id

        return WarningUpdate(
            result=_build_result(decision, evidence, message),
            state=state,
            notify_event_id=notify_event_id,
        )