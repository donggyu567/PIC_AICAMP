"""Pure scoring functions for Shim-Pick analysis."""

from typing import Mapping

from .config import FACTOR_MIN_SCORE, INSTALLATION_WEIGHTS, MAIN_FACTOR_TOP_K, RISK_THRESHOLDS, VULNERABILITY_WEIGHTS


def weighted_score(scores: Mapping[str, float], weights: Mapping[str, float]) -> float:
    return sum(scores[name] * weight for name, weight in weights.items())


def risk_level(vulnerability_score: float) -> str:
    if vulnerability_score < RISK_THRESHOLDS["LOW"]:
        return "LOW"
    if vulnerability_score < RISK_THRESHOLDS["MODERATE"]:
        return "MODERATE"
    if vulnerability_score < RISK_THRESHOLDS["HIGH"]:
        return "HIGH"
    return "VERY_HIGH"


def placement_risk_level(placement_risk_score: float) -> str:
    """Classify the separate MVP v0.1 placement-aware residual-risk score."""
    return risk_level(placement_risk_score)


def blind_spot(current_covered: bool | None, vulnerability_risk_level: str | None) -> bool | None:
    """Apply the official blind-spot rule using structural vulnerability risk."""
    if current_covered is None or vulnerability_risk_level is None:
        return None
    return current_covered is False and vulnerability_risk_level in {"HIGH", "VERY_HIGH"}


def main_factors(scores: Mapping[str, float]) -> list[str]:
    labels = {
        "heat": "HIGH_HEAT",
        "elderly": "HIGH_ELDERLY_RATIO",
        "farmland": "HIGH_FARMLAND_RATIO",
        "coverage_gap": "LOW_SHELTER_ACCESSIBILITY",
    }
    # The fixed secondary order makes equal scores reproducible.
    order = {name: position for position, name in enumerate(labels)}
    selected = [(name, score) for name, score in scores.items() if score >= FACTOR_MIN_SCORE]
    selected.sort(key=lambda item: (-item[1], order[item[0]]))
    return [labels[name] for name, _ in selected[:MAIN_FACTOR_TOP_K]]
