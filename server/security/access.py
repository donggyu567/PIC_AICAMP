"""HTTP와 WebSocket이 공유하는 기기 인증 및 통화 소유권 검사."""

from pathlib import Path

from fastapi import HTTPException, Request

from server.security.device_store import ConversationOwnershipError, DeviceStore, DeviceStoreError
from server.security import limits


device_store = DeviceStore(Path(__file__).resolve().parents[2] / "backend" / "data" / "security" / "devices.json")


def authenticate_header(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, separator, token = authorization.partition(" ")
    if not separator or scheme.lower() != "bearer" or not token or " " in token:
        return None
    return device_store.authenticate(token)


def authenticated_device(request: Request) -> str:
    peer = request.client.host if request.client else "unknown"
    if limits.invalid_auth_attempts.blocked(peer):
        raise HTTPException(status_code=429, detail="인증 요청이 너무 많습니다.", headers={"Retry-After": "60"})
    try:
        owner = authenticate_header(request.headers.get("authorization"))
    except DeviceStoreError:
        raise HTTPException(status_code=503, detail="인증 저장소를 사용할 수 없습니다.") from None
    if owner is None:
        limits.invalid_auth_attempts.allow(peer)
        raise HTTPException(status_code=401, detail="기기 인증이 필요합니다.", headers={"WWW-Authenticate": "Bearer"})
    return owner


def require_conversation_owner(owner: str, conversation_id: str) -> None:
    try:
        device_store.require_owner(owner, conversation_id)
    except ConversationOwnershipError:
        # 존재하지 않는 통화와 다른 기기의 통화를 구분하지 않는다.
        raise HTTPException(status_code=404, detail="통화를 찾을 수 없습니다.") from None
    except DeviceStoreError:
        raise HTTPException(status_code=503, detail="인증 저장소를 사용할 수 없습니다.") from None
