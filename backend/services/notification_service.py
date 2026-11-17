"""통화 화면용 경고 알림을 조회하고 수신확인을 저장한다."""

from copy import deepcopy
from datetime import datetime, timezone

from backend.schemas import NotificationListResponse, NotificationRecord
from backend.stores.analysis_file_store import AnalysisFileStore
from backend.stores.conversation_locks import ConversationLocks
from models.warning_manager.contracts import WarningResult


class NotificationNotFoundError(LookupError):
    """요청한 통화 또는 해당 통화의 알림이 존재하지 않는다."""


def create_notification(
    conversation_id: str, event_id: str, result: WarningResult,
) -> NotificationRecord:
    """이벤트 발생 당시의 문구·근거를 이후 경고 갱신과 분리해 보관한다."""
    return NotificationRecord(
        event_id=event_id,
        conversation_id=conversation_id,
        created_at=datetime.now(timezone.utc),
        warning=deepcopy(result["warning"]),
        evidence=deepcopy(result["evidence"]),
    )


def expire_notifications(
    notifications: list[NotificationRecord], ended_at: datetime,
) -> list[NotificationRecord]:
    """통화 종료 시 미확인 알림만 만료한다. 확인된 알림의 시각은 유지한다."""
    return [
        NotificationRecord.model_validate({
            **notification.model_dump(),
            "status": "expired",
            "expired_at": ended_at,
        })
        if notification.status == "pending" else notification
        for notification in notifications
    ]


class NotificationService:
    def __init__(
        self, store: AnalysisFileStore, locks: ConversationLocks,
    ) -> None:
        self._store = store
        self._locks = locks

    def list_pending(self, conversation_id: str) -> NotificationListResponse:
        """조회는 수신확인이 아니다. 확인 전에는 같은 ID를 다시 제공한다."""
        with self._locks.hold(conversation_id):
            snapshot = self._store.load(conversation_id)
            if snapshot is None:
                raise NotificationNotFoundError("알림을 조회할 통화 기록이 없습니다.")
            notifications = (
                [item for item in snapshot.notifications if item.status == "pending"]
                if snapshot.conversation_status == "active" else []
            )
            return NotificationListResponse(
                conversation_id=snapshot.conversation_id,
                conversation_status=snapshot.conversation_status,
                notifications=notifications,
            )

    def acknowledge(self, conversation_id: str, event_id: str) -> NotificationRecord:
        """최초 수신확인만 저장한다. 반복·늦은 요청은 기존 처리 결과를 반환한다."""
        with self._locks.hold(conversation_id):
            snapshot = self._store.load(conversation_id)
            if snapshot is None:
                raise NotificationNotFoundError("알림을 확인할 통화 기록이 없습니다.")

            for index, notification in enumerate(snapshot.notifications):
                if notification.event_id != event_id:
                    continue
                if notification.status != "pending":
                    return notification

                acknowledged = NotificationRecord.model_validate({
                    **notification.model_dump(),
                    "status": "acknowledged",
                    "acknowledged_at": datetime.now(timezone.utc),
                })
                notifications = [*snapshot.notifications]
                notifications[index] = acknowledged
                updated = snapshot.with_updates(
                    notifications=notifications,
                    pending_notification_ids=[
                        item.event_id for item in notifications
                        if item.status == "pending"
                    ],
                )
                # 저장 성공 이후에만 확인 완료를 반환한다.
                self._store.save(updated)
                return acknowledged

            raise NotificationNotFoundError("해당 통화의 알림을 찾을 수 없습니다.")
