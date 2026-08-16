"""Public orchestration for model-agnostic risk-speech analysis."""

from __future__ import annotations

from .preprocessing import preprocess_text
from .risk_assessor import RiskAssessor, UnconfiguredRiskAssessor
from .schemas import RiskAssessment


def analyze_risk(
    text: object,
    *,
    assessor: RiskAssessor | None = None,
    max_length: int | None = None,
) -> RiskAssessment:
    """Preprocess text and delegate its assessment to an injected assessor.

    ``max_length`` is optional because no project-wide length policy is set.
    When no assessor is supplied, this function returns an explicitly
    unconfigured assessment and makes no claim about risk.
    """

    normalized_text = preprocess_text(text, max_length=max_length)
    active_assessor = assessor if assessor is not None else UnconfiguredRiskAssessor()
    return active_assessor.assess(normalized_text)
