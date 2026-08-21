"""Public API for the masked STT correction stage."""

from .client import LLMClient, LLMClientError

from .contracts import (
    ALLOWED_MASKED_TYPES,
    SUPPORTED_SCHEMA_VERSION,
    UNCLEAR_TOKEN,
    ContractError,
    CorrectionResult,
    MaskedTranscript,
    validate_correction_against_input,
    validate_masking_token_preservation,
)
from .engine import CorrectionEngine, CorrectionValidationError
from .parser import LLMResponseError, ParsedCorrection, parse_correction_response
from .prompts import SYSTEM_PROMPT, build_user_prompt

__all__ = [
    "ALLOWED_MASKED_TYPES",
    "SUPPORTED_SCHEMA_VERSION",
    "UNCLEAR_TOKEN",
    "ContractError",
    "CorrectionEngine",
    "CorrectionResult",
    "CorrectionValidationError",
    "LLMClient",
    "LLMClientError",
    "LLMResponseError",
    "MaskedTranscript",
    "ParsedCorrection",
    "SYSTEM_PROMPT",
    "build_user_prompt",
    "parse_correction_response",
    "validate_correction_against_input",
    "validate_masking_token_preservation",
]
