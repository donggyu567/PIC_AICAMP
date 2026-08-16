"""Model-independent assessor contract.

Concrete implementations may later call a local model, an approved API, or a
rules engine.  This module deliberately contains no decision criteria.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .schemas import RiskAssessment


@runtime_checkable
class RiskAssessor(Protocol):
    """A component that assesses already preprocessed utterance text."""

    def assess(self, text: str) -> RiskAssessment:
        """Return an assessment without mutating the input."""


class UnconfiguredRiskAssessor:
    """Safe default used until the team selects a real assessor."""

    def assess(self, text: str) -> RiskAssessment:
        return RiskAssessment(
            reason="Risk assessment is unavailable until an assessor is configured."
        )
