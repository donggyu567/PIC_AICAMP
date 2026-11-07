from pathlib import Path

from dotenv import load_dotenv

# 실행 위치와 무관하게 프로젝트 루트 설정을 읽고, 명시한 환경변수는 유지한다.
load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False, encoding="utf-8-sig")

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from server.lifespan import lifespan
from server.analysis.router import router as analysis_router
from server.analysis.lifecycle_router import router as lifecycle_router
from server.stt.router import router as stt_router


app = FastAPI(title="PIC Server", version="2.0.0", lifespan=lifespan)
app.include_router(stt_router)
app.include_router(analysis_router)
app.include_router(lifecycle_router)


@app.exception_handler(RequestValidationError)
async def handle_invalid_request(request, error):
    # 검증 실패 응답에 잘못 전송된 원문 입력을 되돌려 보내지 않는다.
    return JSONResponse(status_code=422, content={"detail": "요청 필드와 형식을 확인해 주세요."})


@app.get("/health", tags=["상태 확인"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}
