"""FastAPI entrypoint for masked-transcript correction."""

from __future__ import annotations

from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from backend.api.routes import router
from backend.config import Settings
from backend.dependencies import build_services
from backend.errors import PipelineError
from models.llm_correction import LLMClient


MAX_REQUEST_BYTES = 64 * 1024


def create_app(
    *,
    settings: Settings | None = None,
    llm_client: LLMClient | None = None,
) -> FastAPI:
    resolved_settings = settings if settings is not None else Settings.from_environment()
    app = FastAPI(
        title="PIC Masked STT Correction API",
        version="1.0.0",
    )
    app.state.services = build_services(
        resolved_settings,
        llm_client=llm_client,
    )

    @app.middleware("http")
    async def request_metadata_and_size_limit(request: Request, call_next):
        request_id = uuid4().hex
        request.state.request_id = request_id
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                declared_size = int(content_length)
            except ValueError:
                declared_size = -1
            if declared_size < 0:
                response = _error_response(
                    status_code=400,
                    code="INVALID_CONTENT_LENGTH",
                    message="The Content-Length header is invalid",
                    request_id=request_id,
                )
                response.headers["X-Request-ID"] = request_id
                return response
            if declared_size > MAX_REQUEST_BYTES:
                response = _error_response(
                    status_code=413,
                    code="REQUEST_TOO_LARGE",
                    message="The request body exceeds the allowed size",
                    request_id=request_id,
                )
                response.headers["X-Request-ID"] = request_id
                return response

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request,
        _error: RequestValidationError,
    ) -> JSONResponse:
        return _error_response(
            status_code=422,
            code="INVALID_REQUEST",
            message="The request JSON does not match the API schema",
            request_id=_request_id(request),
        )

    @app.exception_handler(PipelineError)
    async def pipeline_error_handler(
        request: Request,
        error: PipelineError,
    ) -> JSONResponse:
        return _error_response(
            status_code=error.status_code,
            code=error.code,
            message=error.public_message,
            request_id=_request_id(request),
        )

    @app.exception_handler(Exception)
    async def unexpected_error_handler(
        request: Request,
        _error: Exception,
    ) -> JSONResponse:
        return _error_response(
            status_code=500,
            code="INTERNAL_ERROR",
            message="The request could not be processed",
            request_id=_request_id(request),
        )

    app.include_router(router)
    return app


def _request_id(request: Request) -> str:
    value = getattr(request.state, "request_id", None)
    return value if isinstance(value, str) and value else uuid4().hex


def _error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    request_id: str,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "request_id": request_id,
            }
        },
    )


app = create_app()
