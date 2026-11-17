"""팀원 경고 구현체의 호출·반환 계약을 검증한다. 경고 정책은 구현하지 않는다."""

import json
import logging
from copy import deepcopy
from dataclasses import asdict, replace
from math import isfinite

from pydantic import TypeAdapter

from models.warning_manager.contracts import (
    CalculationResult, ConversationWarningState, ModelRiskResult, WarningConfig,
    WarningResult, WarningUpdate,
)
from models.warning_manager.warning_manager import WarningManager


logger = logging.getLogger(__name__)
warning_update_adapter = TypeAdapter(WarningUpdate)


class WarningIntegrationError(RuntimeError):
    """경고 구현체 미연결·호출 실패 또는 잘못된 반환값."""


def _validate_evidence(result: WarningResult) -> None:
    evidence = result["evidence"]
    items = [item for item in (evidence["recent"], evidence["highest"]) if item is not None]
    for event in evidence["cumulative_events"]:
        if event["trigger_utterance_id"] < 1 or not 0 <= event["risk_score"] <= 100:
            raise ValueError("누적 경고 근거의 ID 또는 점수 범위가 잘못되었습니다.")
        items.extend(event["utterances"])
    for item in items:
        if item["utterance_id"] < 1 or not item["text"].strip():
            raise ValueError("근거의 ID 또는 문장이 잘못되었습니다.")
        if not isfinite(item["risk_score"]) or not 0 <= item["risk_score"] <= 100:
            raise ValueError("근거 점수는 0~100이어야 합니다.")
        if len(item["risk_types"]) != len(set(item["risk_types"])):
            raise ValueError("근거의 유형이 중복되었습니다.")


def _validate_conversation_end(
    update: WarningUpdate,
    model_result: ModelRiskResult,
    calculation_result: CalculationResult | None,
    previous_state: ConversationWarningState | None,
    previous_result: WarningResult | None,
) -> None:
    """종료 시 상태와 종료 순서 외의 기록 변경을 차단한다."""
    if model_result.analysis_status == "error":
        if calculation_result is not None:
            raise ValueError("분석 실패에는 계산 결과가 없어야 합니다.")
    else:
        if calculation_result is None or previous_state is None:
            raise ValueError("성공한 통화 종료에는 기존 계산과 경고 상태가 필요합니다.")
        if (
            calculation_result.conversation_id != model_result.conversation_id
            or calculation_result.utterance_id != model_result.utterance_id
            or calculation_result.revision != model_result.revision
            or not calculation_result.window_utterances
            or calculation_result.window_utterances[-1].utterance != model_result
            or calculation_result.cumulative_score != previous_state.cumulative_score
        ):
            raise ValueError("통화 종료에 전달한 마지막 계산 결과가 일치하지 않습니다.")

    expected_state = previous_state
    if previous_state is not None and previous_state.status == "active":
        if not previous_state.events:
            raise ValueError("종료할 활성 경고 이벤트가 없습니다.")
        latest = previous_state.events[-1]
        if (
            latest.closed_sequence is not None
            or model_result.sequence < latest.last_sequence
        ):
            raise ValueError("경고 이벤트의 종료 순서가 올바르지 않습니다.")
        expected_state = replace(
            previous_state,
            status="previous_warning",
            events=previous_state.events[:-1] + (
                replace(latest, closed_sequence=model_result.sequence),
            ),
        )
    if update.state != expected_state:
        raise ValueError("통화 종료 시 기존 점수와 경고 이력을 보존해야 합니다.")
    if update.notify_event_id is not None:
        raise ValueError("통화 종료 시 새로운 알림을 요청할 수 없습니다.")

    expected_evidence = (
        previous_result["evidence"] if previous_result is not None else
        {"recent": None, "highest": None, "cumulative_events": []}
    )
    if update.result["evidence"] != expected_evidence:
        raise ValueError("통화 종료 시 기존 경고 근거를 보존해야 합니다.")
    expected_status = expected_state.status if expected_state is not None else "none"
    expected_reason = (
        expected_state.events[-1].reason
        if expected_state is not None and expected_state.status != "none"
        else None
    )
    warning = update.result["warning"]
    if warning["status"] != expected_status or warning["reason"] != expected_reason:
        raise ValueError("통화 종료 시 경고 상태와 기존 사유를 보존해야 합니다.")


def update_warning(
    manager: WarningManager,
    model_result: ModelRiskResult,
    calculation_result: CalculationResult | None,
    previous_state: ConversationWarningState | None,
    config: WarningConfig,
    previous_result: WarningResult | None = None,
    *,
    conversation_ended: bool = False,
) -> WarningUpdate:
    try:
        if not isinstance(conversation_ended, bool):
            raise ValueError("conversation_ended는 불리언이어야 합니다.")
        # 구현체가 내부 dict/list를 변경해도 서버의 이전 기록은 보존한다.
        raw = manager.update_warning(
            deepcopy(model_result), deepcopy(calculation_result),
            deepcopy(previous_state), deepcopy(config),
            is_replay=False, conversation_ended=conversation_ended,
        )
        if not isinstance(raw, WarningUpdate):
            raise ValueError("WarningUpdate 결과가 필요합니다.")
        # dataclass는 타입·범위를 자동 검증하지 않는다. 중첩 구조까지 다시 읽는다.
        update = warning_update_adapter.validate_json(
            json.dumps(asdict(raw), ensure_ascii=False, allow_nan=False), strict=True,
        )
        _validate_evidence(update.result)
        warning = update.result["warning"]
        if not warning["message"].strip():
            raise ValueError("경고 안내 문구가 필요합니다.")
        if (warning["status"] == "none") != (warning["reason"] is None):
            raise ValueError("경고 상태와 사유가 일치하지 않습니다.")
        if update.state is not None:
            if update.state.conversation_id != model_result.conversation_id:
                raise ValueError("다른 통화의 경고 상태가 반환되었습니다.")
            if update.state.config != config:
                raise ValueError("통화의 경고 설정이 변경되었습니다.")
            if update.state.status != warning["status"]:
                raise ValueError("응답과 저장용 경고 상태가 다릅니다.")

        if conversation_ended:
            _validate_conversation_end(
                update, model_result, calculation_result, previous_state,
                previous_result,
            )
        elif model_result.analysis_status == "error":
            if calculation_result is not None or update.state != previous_state:
                raise ValueError("분석 실패 시 기존 경고 상태를 유지해야 합니다.")
            if update.notify_event_id is not None:
                raise ValueError("분석 실패 시 알림을 요청할 수 없습니다.")
            expected_evidence = (
                previous_result["evidence"] if previous_result is not None else
                {"recent": None, "highest": None, "cumulative_events": []}
            )
            if update.result["evidence"] != expected_evidence:
                raise ValueError("분석 실패 시 기존 경고 근거를 유지해야 합니다.")
            if previous_state is None and warning["status"] != "none":
                raise ValueError("첫 분석 실패에 기존 경고가 있을 수 없습니다.")
        else:
            if update.state is None or calculation_result is None:
                raise ValueError("성공 분석의 경고 상태와 계산 결과가 필요합니다.")
            if update.state.cumulative_score != calculation_result.cumulative_score:
                raise ValueError("경고 상태의 누적 점수가 계산 결과와 다릅니다.")

        if update.notify_event_id is not None:
            if (
                not update.notify_event_id.strip()
                or len(update.notify_event_id) > 200
                or update.state is None
            ):
                raise ValueError("알림 이벤트 ID가 올바르지 않습니다.")
            if warning["status"] != "active" or warning["reason"] is None:
                raise ValueError("새 알림에는 활성 경고와 사유가 필요합니다.")
            if update.notify_event_id not in {event.event_id for event in update.state.events}:
                raise ValueError("알림 대상 이벤트가 저장용 상태에 없습니다.")
        return update
    except Exception as error:
        logger.warning("WARNING_MODULE_ERROR %s", type(error).__name__)
        raise WarningIntegrationError("경고 모듈의 처리 결과를 얻지 못했습니다.") from None
