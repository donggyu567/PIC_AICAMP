"""Deterministic 0-100 feature normalization."""

from typing import Iterable

from .config import (
    MIN_SAMPLES_FOR_ROBUST_SCALING,
    NORMALIZATION_LOWER_PERCENTILE,
    NORMALIZATION_UPPER_PERCENTILE,
)


def normalize(values: Iterable[float]) -> list[float]:
    """Normalize values using robust min-max for 20+ samples, otherwise min-max."""
    items = [float(value) for value in values]
    if not items:
        return []
    if len(items) >= MIN_SAMPLES_FOR_ROBUST_SCALING:
        lower = percentile(items, NORMALIZATION_LOWER_PERCENTILE)
        upper = percentile(items, NORMALIZATION_UPPER_PERCENTILE)
        return [_scale(min(max(value, lower), upper), lower, upper) for value in items]
    lower, upper = min(items), max(items)
    return [_scale(value, lower, upper) for value in items]


def percentile(values: list[float], percent: float) -> float:
    """Return an interpolated percentile without a numerical dependency."""
    ordered = sorted(values)
    index = (len(ordered) - 1) * percent / 100
    lower, upper = int(index), min(int(index) + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)


def _scale(value: float, lower: float, upper: float) -> float:
    if upper == lower:
        return 50.0
    return max(0.0, min(100.0, (value - lower) / (upper - lower) * 100))
