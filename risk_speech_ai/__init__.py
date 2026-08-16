"""Minimal, model-agnostic interfaces for risk-speech analysis."""

from .analyzer import analyze_risk
from .risk_assessor import RiskAssessor, UnconfiguredRiskAssessor
from .schemas import RiskAssessment

__all__ = [
    "RiskAssessment",
    "RiskAssessor",
    "UnconfiguredRiskAssessor",
    "analyze_risk",
]
