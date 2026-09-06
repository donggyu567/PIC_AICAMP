"""Versioned HTTP endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response, status

from backend.dependencies import Services
from backend.schemas import (
    HealthResponse,
    MaskedTranscriptRequest,
    ProcessUtteranceResponse,
)


router = APIRouter()


def get_services(request: Request) -> Services:
    return request.app.state.services


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.post(
    "/api/v1/utterances",
    response_model=ProcessUtteranceResponse,
    responses={
        409: {"description": "Conversation or idempotency conflict"},
        422: {"description": "Invalid masked-transcript contract"},
        502: {"description": "Correction provider failure"},
    },
)
def process_utterance(
    payload: MaskedTranscriptRequest,
    response: Response,
    services: Services = Depends(get_services),
) -> ProcessUtteranceResponse:
    result = services.pipeline.process(payload.model_dump())
    response.status_code = (
        status.HTTP_201_CREATED
        if result.status == "created"
        else status.HTTP_200_OK
    )
    return ProcessUtteranceResponse(
        status=result.status,
        context=result.context.to_dict(),
        saved_as=result.storage_key,
    )


@router.get(
    "/api/v1/conversations/{conversation_id}/context",
    response_model=ProcessUtteranceResponse,
)
def get_latest_context(
    conversation_id: str,
    services: Services = Depends(get_services),
) -> ProcessUtteranceResponse:
    result = services.pipeline.get_latest(conversation_id)
    return ProcessUtteranceResponse(
        status="cached",
        context=result.context.to_dict(),
        saved_as=result.storage_key,
    )
