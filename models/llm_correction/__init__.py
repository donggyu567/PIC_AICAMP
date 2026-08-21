"""Public data contracts for the masked STT correction stage."""

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

__all__ = [
    "ALLOWED_MASKED_TYPES",
    "SUPPORTED_SCHEMA_VERSION",
    "UNCLEAR_TOKEN",
    "ContractError",
    "CorrectionResult",
    "MaskedTranscript",
    "validate_correction_against_input",
    "validate_masking_token_preservation",
]
