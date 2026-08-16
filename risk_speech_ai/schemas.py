"""Data structures shared by the risk-speech analysis module.

Risk levels, score ranges, and decision criteria have not been decided yet.
Accordingly, every decision-related field is optional.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RiskAssessment:
    """A model's assessment of one preprocessed utterance.

    ``None`` means that the relevant value is unknown or has not been produced
    by the configured assessor; it does not mean that the utterance is safe.
    """

    is_risky: bool | None = None
    risk_level: str | None = None
    risk_score: float | None = None
    reason: str | None = None
