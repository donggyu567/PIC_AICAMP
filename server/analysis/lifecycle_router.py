"""기존 통화 종료·알림 서비스를 새 서버에 공개한다."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import Field

from backend.schemas import (
    ConversationEndRequest, ConversationEndResponse, NotificationAckRequest,
    NotificationListResponse, NotificationRecord,
)
from backend.services import analysis_service
from backend.services.notification_service import NotificationService
from server.analysis.router import run_analysis
from server.security.access import authenticated_device, require_conversation_owner


router = APIRouter(prefix="/api/v1", tags=["통화·알림"])


class FinalizeConversationRequest(ConversationEndRequest):
    # STT stopped의 마지막 번호. 분석 완료를 기다린 뒤 최종 종료를 요청한다.
    last_utterance_id: int = Field(ge=1)


@router.post("/conversations/withdraw")
def withdraw_conversation(payload: ConversationEndRequest, owner: Annotated[str, Depends(authenticated_device)]):
    """삭제 완료 전에는 성공을 반환하지 않으며, 반복 요청을 허용한다."""
    require_conversation_owner(owner, payload.conversation_id)
    run_analysis(analysis_service.withdraw_conversation, payload.conversation_id)
    return {"conversation_id": payload.conversation_id, "status": "deleted"}


def get_notification_service() -> NotificationService:
    return NotificationService(analysis_service.analysis_store, analysis_service.conversation_locks)


@router.post("/conversations/end", response_model=ConversationEndResponse)
def finish_conversation(payload: FinalizeConversationRequest, request: Request, owner: Annotated[str, Depends(authenticated_device)]):
    """마지막 저장 번호 확인 후 경고·미확인 알림을 종료하고 최종 결과를 반환한다."""
    require_conversation_owner(owner, payload.conversation_id)
    return run_analysis(
        analysis_service.end_conversation, payload.conversation_id,
        request.app.state.warning_manager,
        expected_last_utterance_id=payload.last_utterance_id,
    )


@router.get("/notifications", response_model=NotificationListResponse)
def read_notifications(
    conversation_id: Annotated[str, Query(min_length=1, max_length=120, pattern=r"\S")],
    response: Response,
    service: Annotated[NotificationService, Depends(get_notification_service)],
    owner: Annotated[str, Depends(authenticated_device)],
):
    require_conversation_owner(owner, conversation_id)
    response.headers["Cache-Control"] = "no-store"
    return run_analysis(service.list_pending, conversation_id)


@router.post("/notifications/ack", response_model=NotificationRecord)
def acknowledge_notification(
    payload: NotificationAckRequest,
    service: Annotated[NotificationService, Depends(get_notification_service)],
    owner: Annotated[str, Depends(authenticated_device)],
):
    require_conversation_owner(owner, payload.conversation_id)
    return run_analysis(service.acknowledge, payload.conversation_id, payload.event_id)
