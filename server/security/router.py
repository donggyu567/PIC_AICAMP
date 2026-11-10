"""시연용 기기 등록. 발급된 토큰은 HTTPS 응답으로 한 번만 전달한다."""

from fastapi import APIRouter, HTTPException, Request, Response

from server.security import access, limits
from server.security.device_store import DeviceStoreError

router = APIRouter(prefix="/api/v1/devices", tags=["기기 인증"])


@router.post("/register", status_code=201)
def register_device(request: Request, response: Response) -> dict[str, str]:
    peer = request.client.host if request.client else "unknown"
    if not limits.device_registrations.allow(peer) or not limits.total_device_registrations.allow("all"):
        raise HTTPException(429, "기기 등록 요청이 너무 많습니다.")
    try:
        token = access.device_store.issue_device()
    except DeviceStoreError:
        raise HTTPException(503, "기기 등록을 완료하지 못했습니다.") from None
    response.headers["Cache-Control"] = "no-store"
    return {"token": token}
