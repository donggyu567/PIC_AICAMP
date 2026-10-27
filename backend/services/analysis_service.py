"""분석 결과의 파일 저장·누적 계산·실패 복구·경고 연동을 조율한다."""

from datetime import datetime, timezone
from pathlib import Path

from backend.schemas import (
    CalculationPreviewResponse, ConversationEndResponse, ModelResultRequest,
)
from backend.services.analysis_response import build_analysis_response
from backend.services.notification_service import create_notification, expire_notifications
from backend.services.risk_service import calculate_risk
from backend.services.warning_service import WarningIntegrationError, update_warning
from backend.stores.analysis_file_store import (
    AnalysisAttempt,
    AnalysisFileStore,
    CalculationPolicy,
    ConversationSnapshot,
    StoredAnalysis,
)
from backend.stores.analysis_store import AnalysisConflictError, validate_new_result
from backend.stores.conversation_locks import ConversationLocks
from models.warning_manager.contracts import (
    CalculationResult, ModelRiskResult, WarningConfig, WarningResult,
)
from models.warning_manager.warning_manager import WarningManager


class AnalysisPendingError(AnalysisConflictError):
    """이전 분석 실패를 복구해야 후속 처리가 가능한 경우."""


class AnalysisNotFoundError(LookupError):
    """요청한 통화 기록이 존재하지 않는 경우."""


analysis_store = AnalysisFileStore(
    Path(__file__).resolve().parents[1] / "data" / "analysis"
)
# 같은 통화만 직렬화하며, 처리·대기가 끝난 잠금은 자동으로 정리한다.
conversation_locks = ConversationLocks()

# 신규 통화의 개발 기본값. 기존 통화는 파일에 저장된 설정을 사용한다.
WINDOW_SIZE = 20
RHO = 0.95
B = 0.1
POLICY_VERSION = "risk-policy-v1"

def ensure_conversation_active(
    snapshot: ConversationSnapshot | None,
) -> None:
    """종료된 통화의 분석 결과 변경을 차단한다."""
    if snapshot is not None and snapshot.conversation_status == "ended":
        raise AnalysisConflictError(
            "종료된 통화에는 발화를 추가하거나 분석을 재시도할 수 없습니다."
        )

def prepare_warning_session(
    snapshot: ConversationSnapshot | None, manager: WarningManager | None,
) -> WarningConfig | None:
    """통화 중 경고 연동을 누락하거나 과거 이력 없이 시작하는 것을 막는다."""
    if snapshot is not None and snapshot.warning_config is not None:
        if manager is None:
            raise WarningIntegrationError("이 통화를 처리하려면 경고 모듈 연결이 필요합니다.")
        return snapshot.warning_config
    if manager is None:
        return None
    if snapshot is not None:
        raise AnalysisConflictError(
            "경고 없이 시작한 통화는 새 통화 ID로 경고 연동을 시작해야 합니다."
        )
    return WarningConfig()


def _process_warning(
    snapshot: ConversationSnapshot | None,
    manager: WarningManager | None,
    current: ModelRiskResult,
    calculation: CalculationResult | None,
    config: WarningConfig | None,
) -> tuple[WarningResult | None, dict[str, object]]:
    if config is None:
        return None, {}
    previous_result = None
    if snapshot is not None:
        last = snapshot.records[-1].response
        previous_result = {"warning": last.warning, "evidence": last.evidence}
    update = update_warning(
        manager, current, calculation,
        snapshot.warning_state if snapshot is not None else None,
        config, previous_result,
    )
    notifications = list(snapshot.notifications) if snapshot is not None else []
    # 수신확인된 이벤트도 보존하므로 같은 ID를 다시 요청해도 재등록하지 않는다.
    if update.notify_event_id is not None and update.notify_event_id not in {
        item.event_id for item in notifications
    }:
        notifications.append(create_notification(
            current.conversation_id, update.notify_event_id, update.result,
        ))
    return update.result, {
        "warning_config": config,
        "warning_state": update.state,
        "notifications": notifications,
        "pending_notification_ids": [
            item.event_id for item in notifications if item.status == "pending"
        ],
    }


def process_model_result(
    payload: ModelResultRequest,
    warning_manager: WarningManager | None = None,
) -> CalculationPreviewResponse:
    """직접 전달받은 신규 분석 결과의 처리 시작점."""
    with conversation_locks.hold(payload.conversation_id):
        snapshot = analysis_store.load(payload.conversation_id)
        ensure_conversation_active(snapshot)
        config = prepare_warning_session(snapshot, warning_manager)

        return _process_model_result_locked(
            payload, snapshot, warning_manager, config,
        )


def _process_model_result_locked(
    payload: ModelResultRequest,
    snapshot: ConversationSnapshot | None,
    warning_manager: WarningManager | None,
    warning_config: WarningConfig | None,
) -> CalculationPreviewResponse:
    """계산·경고 처리·저장. 호출자는 통화 잠금과 경고 설정을 준비해야 한다."""
    current = payload.to_model_result()

    records = snapshot.records if snapshot is not None else []
    policy = snapshot.policy if snapshot is not None else CalculationPolicy(
        window_size=WINDOW_SIZE,
        rho=RHO,
        b=B,
        policy_version=POLICY_VERSION,
    )

    # 저장 파일 전체의 무결성은 load에서 검사했다. 신규 결과만 확인한다.
    validate_new_result(
        payload,
        seen_ids={record.model_result.utterance_id for record in records},
        expected_sequence=len(records) + 1,
    )

    if records and records[-1].model_result.analysis_status == "error":
        raise AnalysisPendingError(
            "이전 분석 실패를 복구한 뒤 순서대로 재처리해야 합니다."
        )

    calculation = _calculate_current(records, current, policy)

    warning_result, warning_fields = _process_warning(
        snapshot, warning_manager, current, calculation, warning_config,
    )
    response = build_analysis_response(
        current, calculation, warning_result,
    )

    updated = ConversationSnapshot(
        conversation_id=current.conversation_id,
        conversation_status=(
            snapshot.conversation_status if snapshot is not None else "active"
        ),
        ended_at=snapshot.ended_at if snapshot is not None else None,
        policy=policy,
        records=[
            *records,
            StoredAnalysis(model_result=payload, response=response),
        ],
        **warning_fields,
    )

    # 계산·경고 처리가 끝난 결과를 저장하고, 저장 성공 후 반환한다.
    analysis_store.save(updated)
    return response


def _calculate_current(
    previous_records: list[StoredAnalysis],
    current: ModelRiskResult,
    policy: CalculationPolicy,
) -> CalculationResult | None:
    """현재 발화를 포함한 계산 창만 공통 모델 객체로 변환한다."""
    if current.analysis_status == "error":
        return None
    start = max(0, len(previous_records) - policy.window_size + 1)
    window = [
        record.model_result.to_model_result()
        for record in previous_records[start:]
    ]
    return calculate_risk(window + [current], **policy.model_dump())


def retry_model_result(
    payload: ModelResultRequest,
    warning_manager: WarningManager | None = None,
) -> CalculationPreviewResponse:
    """마지막 실패 발화의 재분석 결과를 등록한다."""
    with conversation_locks.hold(payload.conversation_id):
        snapshot = analysis_store.load(payload.conversation_id)
        if snapshot is None:
            raise AnalysisNotFoundError("재시도할 통화 기록이 없습니다.")
        ensure_conversation_active(snapshot)
        config = prepare_warning_session(snapshot, warning_manager)
        return _retry_model_result_locked(payload, snapshot, warning_manager, config)


def _retry_model_result_locked(
    payload: ModelResultRequest,
    snapshot: ConversationSnapshot,
    warning_manager: WarningManager | None,
    warning_config: WarningConfig | None,
) -> CalculationPreviewResponse:
    """실패 이력 보존·재계산. 호출자는 통화 잠금과 경고 설정을 준비해야 한다."""
    current = payload.to_model_result()

    failed = snapshot.records[-1]
    if failed.model_result.analysis_status != "error":
        raise AnalysisConflictError("마지막 발화가 실패 상태일 때만 재시도할 수 있습니다.")

    # 같은 문장의 같은 버전을 재분석한다. 문장 정정은 별도 재처리가 필요하다.
    for field in (
        "conversation_id", "utterance_id", "revision", "sequence", "tuned_text",
    ):
        if getattr(current, field) != getattr(failed.model_result, field):
            raise AnalysisConflictError(
                "재시도 결과의 발화 ID·순서·버전·문장이 실패 기록과 같아야 합니다."
            )

    calculation = _calculate_current(snapshot.records[:-1], current, snapshot.policy)
    warning_result, warning_fields = _process_warning(
        snapshot, warning_manager, current, calculation, warning_config,
    )
    response = build_analysis_response(current, calculation, warning_result)

    replacement = StoredAnalysis(
        model_result=payload,
        response=response,
        previous_attempts=[
            *failed.previous_attempts,
            AnalysisAttempt(
                model_result=failed.model_result, response=failed.response,
            ),
        ],
    )
    updated = ConversationSnapshot(
        conversation_id=current.conversation_id,
        conversation_status=snapshot.conversation_status,
        ended_at=snapshot.ended_at,
        policy=snapshot.policy,
        records=[*snapshot.records[:-1], replacement],
        **warning_fields,
    )
    analysis_store.save(updated)
    return response


def end_conversation(
    conversation_id: str, warning_manager: WarningManager | None = None,
) -> ConversationEndResponse:
    """경고 종료·알림 만료·통화 종료를 함께 저장하고 같은 최종 결과를 반환한다."""
    with conversation_locks.hold(conversation_id):
        snapshot = analysis_store.load(conversation_id)
        if snapshot is None:
            raise AnalysisNotFoundError("종료할 통화 기록이 없습니다.")

        # 이전 버전이 종료 상태만 저장한 통화도 최초 한 번 경고를 마무리한다.
        needs_warning_end = (
            snapshot.warning_config is not None and snapshot.final_warning_result is None
        )
        if snapshot.conversation_status != "ended" or needs_warning_end:
            final_result = snapshot.final_warning_result
            final_state = snapshot.warning_state
            if needs_warning_end:
                if warning_manager is None:
                    raise WarningIntegrationError("경고를 종료하려면 경고 모듈 연결이 필요합니다.")
                last = snapshot.records[-1]
                current = last.model_result.to_model_result()
                calculation = _calculate_current(snapshot.records[:-1], current, snapshot.policy)
                update = update_warning(
                    warning_manager, current, calculation, snapshot.warning_state,
                    snapshot.warning_config,
                    {"warning": last.response.warning, "evidence": last.response.evidence},
                    conversation_ended=True,
                )
                final_result, final_state = update.result, update.state
            ended_at = snapshot.ended_at or datetime.now(timezone.utc)
            notifications = expire_notifications(snapshot.notifications, ended_at)
            snapshot = snapshot.with_updates(
                conversation_status="ended",
                ended_at=ended_at,
                warning_state=final_state,
                final_warning_result=final_result,
                notifications=notifications,
                pending_notification_ids=[],
            )
            analysis_store.save(snapshot)

        final_result = snapshot.final_warning_result
        return ConversationEndResponse(
            conversation_id=snapshot.conversation_id,
            ended_at=snapshot.ended_at,
            warning=final_result["warning"] if final_result is not None else None,
            evidence=final_result["evidence"] if final_result is not None else None,
        )


def get_analysis_result(
    conversation_id: str, utterance_id: int | None = None,
) -> CalculationPreviewResponse | None:
    """재계산 없이 저장된 최신 또는 특정 발화의 응답을 조회한다."""
    with conversation_locks.hold(conversation_id):
        snapshot = analysis_store.load(conversation_id)
        if snapshot is None:
            return None
        if utterance_id is None:
            return snapshot.records[-1].response
        for record in snapshot.records:
            if record.model_result.utterance_id == utterance_id:
                return record.response
        return None
