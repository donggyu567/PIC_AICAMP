"""Provider-independent recommendation explanation helpers.

This package only explains deterministic AI outputs.  It never selects a
candidate, recalculates scores, or changes a recommendation.
"""

from .prompt import SYSTEM_PROMPT, build_fallback_explanation, format_percentage
from .schemas import ExplanationInput, ExplanationOutput, build_explanation_input

__all__ = [
    "ExplanationInput",
    "ExplanationOutput",
    "SYSTEM_PROMPT",
    "build_explanation_input",
    "build_fallback_explanation",
    "format_percentage",
]
