"""Application service that turns one masked transcript into a correction."""

from __future__ import annotations

from .client import LLMClient, LLMClientError
from .contracts import (
    ContractError,
    CorrectionResult,
    MaskedTranscript,
    validate_correction_against_input,
)
from .parser import parse_correction_response
from .prompts import SYSTEM_PROMPT, build_user_prompt


class CorrectionValidationError(ValueError):
    """Content-free error raised for an unsafe model correction."""


class CorrectionEngine:
    """Orchestrate prompt creation, LLM invocation, and output validation."""

    def __init__(self, client: LLMClient) -> None:
        if not callable(getattr(client, "complete", None)):
            raise TypeError("client must provide a callable complete method")
        self._client = client

    def correct(self, transcript: MaskedTranscript) -> CorrectionResult:
        """Correct one validated transcript and return a trusted result."""

        if not isinstance(transcript, MaskedTranscript):
            raise TypeError("transcript must be a MaskedTranscript")

        user_prompt = build_user_prompt(transcript.masked_text)
        provider_failed = False
        try:
            response_text = self._client.complete(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=user_prompt,
            )
        except Exception:
            provider_failed = True

        if provider_failed:
            raise LLMClientError("LLM provider request failed")

        parsed = parse_correction_response(response_text)

        validation_failed = False
        try:
            result = CorrectionResult(
                schema_version=transcript.schema_version,
                conversation_id=transcript.conversation_id,
                utterance_id=transcript.utterance_id,
                tuned_text=parsed.tuned_text,
                is_tuned=parsed.tuned_text != transcript.masked_text,
                has_unclear=bool(parsed.unclear_segments),
                unclear_segments=parsed.unclear_segments,
            )
            validate_correction_against_input(transcript, result)
        except ContractError:
            validation_failed = True

        if validation_failed:
            raise CorrectionValidationError(
                "LLM correction result failed validation"
            )

        return result
