"""Strict HTTP request and response schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class StrictApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class MaskedTranscriptRequest(StrictApiModel):
    schema_version: str
    conversation_id: str
    utterance_id: int
    masked_text: str
    has_masked_data: bool
    masked_types: list[str]


class UtterancePayload(StrictApiModel):
    schema_version: str
    conversation_id: str
    utterance_id: int
    masked_text: str
    has_masked_data: bool
    masked_types: list[str]
    tuned_text: str
    is_tuned: bool
    has_unclear: bool
    unclear_segments: list[str]


class ConversationContextPayload(StrictApiModel):
    current: UtterancePayload
    history: list[UtterancePayload]


class ProcessUtteranceResponse(StrictApiModel):
    status: Literal["created", "cached"]
    context: ConversationContextPayload
    saved_as: str


class HealthResponse(StrictApiModel):
    status: Literal["ok"]


class ErrorBody(StrictApiModel):
    code: str
    message: str
    request_id: str


class ErrorResponse(StrictApiModel):
    error: ErrorBody
