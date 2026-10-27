"""Content-free application errors exposed by the HTTP layer."""

from __future__ import annotations


class PipelineError(RuntimeError):
    status_code = 500
    code = "INTERNAL_ERROR"
    public_message = "The request could not be processed"


class RequestContractError(PipelineError):
    status_code = 422
    code = "INVALID_MASKED_TRANSCRIPT"
    public_message = "The masked transcript violates the input contract"


class ConversationConflictError(PipelineError):
    status_code = 409
    code = "CONVERSATION_CONFLICT"
    public_message = "The utterance conflicts with stored conversation state"


class UpstreamCorrectionError(PipelineError):
    status_code = 502
    code = "CORRECTION_PROVIDER_ERROR"
    public_message = "The correction provider did not return a trusted result"


class PersistenceError(PipelineError):
    status_code = 500
    code = "PERSISTENCE_ERROR"
    public_message = "The validated result could not be stored"


class ContextNotFoundError(PipelineError):
    status_code = 404
    code = "CONTEXT_NOT_FOUND"
    public_message = "No stored context exists for this conversation"
