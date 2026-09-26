"""분석 결과의 파일 저장·누적 계산·실패 복구·경고 연동을 조율한다."""

from datetime import datetime, timezone
from pathlib import Path
from threading import RLock

from backend.schemas import (
    CalculationPreviewResponse, ConversationEndResponse, ModelResultRequest,
)
from backend.services.analysis_response import build_analysis_response
from backend.services.risk_service import calculate_risk
from backend.services.warning_service import WarningIntegrationError, update_warning
from backend.stores.analysis_file_store import (
    AnalysisAttempt,
    AnalysisFileStore,
    CalculationPolicy,
    ConversationSnapshot,
    StoredAnalysis,
)
from backend.stores.analysis_store import AnalysisConflictError, AnalysisStore
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
# 통합 처리에서 잠금을 잡은 상태로 계산 서비스를 호출할 수 있다.
analysis_lock = RLock()

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
) -> tuple[WarningResult | None, dict[str, object]]:
    config = prepare_warning_session(snapshot, manager)
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
    pending = list(snapshot.pending_notification_ids) if snapshot is not None else []
    if update.notify_event_id is not None and update.notify_event_id not in pending:
        pending.append(update.notify_event_id)
    return update.result, {
        "warning_config": config,
        "warning_state": update.state,
        "pending_notification_ids": pending,
    }


def process_model_result(
    payload: ModelResultRequest,
    warning_manager: WarningManager | None = None,
) -> CalculationPreviewResponse:
    """직접 전달받은 신규 분석 결과의 처리 시작점."""
    with analysis_lock:
        snapshot = analysis_store.load(payload.conversation_id)
        ensure_conversation_active(snapshot)

        return _process_model_result_locked(
            payload, snapshot, warning_manager,
        )


def _process_model_result_locked(
    payload: ModelResultRequest,
    snapshot: ConversationSnapshot | None,
    warning_manager: WarningManager | None = None,
) -> CalculationPreviewResponse:
    """계산·경고 처리·저장을 수행한다. 호출자는 analysis_lock을 잡아야 한다."""
    current = payload.to_model_result()
    prepare_warning_session(snapshot, warning_manager)

    records = snapshot.records if snapshot is not None else []
    policy = snapshot.policy if snapshot is not None else CalculationPolicy(
        window_size=WINDOW_SIZE,
        rho=RHO,
        b=B,
        policy_version=POLICY_VERSION,
    )

    # 저장된 이력을 복원하고 현재 결과의 순서·중복을 검사한다.
    restored = AnalysisStore()
    for record in records:
        restored.add(record.model_result.to_model_result())

    restored.validate_new(current)
    history = restored.get_history(current.conversation_id)

    if any(item.analysis_status == "error" for item in history):
        raise AnalysisPendingError(
            "이전 분석 실패를 복구한 뒤 순서대로 재처리해야 합니다."
        )

    calculation = None
    if current.analysis_status == "ok":
        calculation = calculate_risk(
            history + [current], **policy.model_dump()
        )

    warning_result, warning_fields = _process_warning(
        snapshot, warning_manager, current, calculation,
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


def retry_model_result(
    payload: ModelResultRequest,
    warning_manager: WarningManager | None = None,
) -> CalculationPreviewResponse:
    """마지막 실패 발화의 재분석 결과를 등록한다."""
    with analysis_lock:
        snapshot = analysis_store.load(payload.conversation_id)
        if snapshot is None:
            raise AnalysisNotFoundError("재시도할 통화 기록이 없습니다.")
        ensure_conversation_active(snapshot)
        return _retry_model_result_locked(payload, snapshot, warning_manager)


def _retry_model_result_locked(
    payload: ModelResultRequest,
    snapshot: ConversationSnapshot,
    warning_manager: WarningManager | None = None,
) -> CalculationPreviewResponse:
    """실패 이력을 보존하며 재계산·저장한다. 호출자는 analysis_lock을 잡아야 한다."""
    current = payload.to_model_result()
    prepare_warning_session(snapshot, warning_manager)

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

    history = [
        record.model_result.to_model_result()
        for record in snapshot.records[:-1]
    ]
    calculation = None
    if current.analysis_status == "ok":
        calculation = calculate_risk(
            history + [current], **snapshot.policy.model_dump()
        )
    warning_result, warning_fields = _process_warning(
        snapshot, warning_manager, current, calculation,
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


def end_conversation(conversation_id: str) -> ConversationEndResponse:
    """분석 기록을 보존하고 종료 상태를 저장한다. 재요청은 최초 종료 시각을 반환한다."""
    with analysis_lock:
        snapshot = analysis_store.load(conversation_id)
        if snapshot is None:
            raise AnalysisNotFoundError("종료할 통화 기록이 없습니다.")

        if snapshot.conversation_status != "ended":
            # 경고 상태·근거·알림 대기 목록과 실패 이력은 그대로 보존한다.
            # strict 검증에서 경고 dataclass를 dict로 바꾸지 않도록 타입을 유지한다.
            data = {
                name: getattr(snapshot, name)
                for name in ConversationSnapshot.model_fields
            }
            data.update(
                conversation_status="ended",
                ended_at=datetime.now(timezone.utc),
            )
            snapshot = ConversationSnapshot.model_validate(data)
            analysis_store.save(snapshot)

        return ConversationEndResponse(
            conversation_id=snapshot.conversation_id,
            ended_at=snapshot.ended_at,
        )


def get_analysis_result(
    conversation_id: str, utterance_id: int | None = None,
) -> CalculationPreviewResponse | None:
    """재계산 없이 저장된 최신 또는 특정 발화의 응답을 조회한다."""
    with analysis_lock:
        snapshot = analysis_store.load(conversation_id)
        if snapshot is None:
            return None
        if utterance_id is None:
            return snapshot.records[-1].response
        for record in snapshot.records:
            if record.model_result.utterance_id == utterance_id:
                return record.response
        return None
