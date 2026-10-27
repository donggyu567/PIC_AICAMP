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
from .output import (
    CorrectionOutputConflictError,
    CorrectionOutputError,
    CorrectionResultStore,
)
from .parser import LLMResponseError, ParsedCorrection, parse_correction_response
from .prompts import SYSTEM_PROMPT, build_user_prompt
from .providers import (
    DEFAULT_OPENAI_MAX_OUTPUT_TOKENS,
    DEFAULT_OPENAI_MAX_RETRIES,
    DEFAULT_OPENAI_MODEL,
    DEFAULT_OPENAI_TIMEOUT_SECONDS,
    OpenAIResponsesClient,
)

__all__ = [
    "ALLOWED_MASKED_TYPES",
    "DEFAULT_OPENAI_MAX_OUTPUT_TOKENS",
    "DEFAULT_OPENAI_MAX_RETRIES",
    "DEFAULT_OPENAI_MODEL",
    "DEFAULT_OPENAI_TIMEOUT_SECONDS",
    "SUPPORTED_SCHEMA_VERSION",
    "UNCLEAR_TOKEN",
    "ContractError",
    "CorrectionEngine",
    "CorrectionOutputConflictError",
    "CorrectionOutputError",
    "CorrectionResult",
    "CorrectionResultStore",
    "CorrectionValidationError",
    "LLMClient",
    "LLMClientError",
    "LLMResponseError",
    "MaskedTranscript",
    "OpenAIResponsesClient",
    "ParsedCorrection",
    "SYSTEM_PROMPT",
    "build_user_prompt",
    "parse_correction_response",
    "validate_correction_against_input",
    "validate_masking_token_preservation",
]
