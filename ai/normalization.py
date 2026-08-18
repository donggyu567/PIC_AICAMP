"""Deterministic 0-100 feature normalization."""

from dataclasses import dataclass
from typing import Iterable

from .config import (
    MIN_SAMPLES_FOR_ROBUST_SCALING,
    NORMALIZATION_LOWER_PERCENTILE,
    NORMALIZATION_UPPER_PERCENTILE,
)


@dataclass(frozen=True)
class NormalizationReference:
    """Fitted bounds used to compare multiple values on one fixed scale."""

    lower: float
    upper: float


def normalize(values: Iterable[float]) -> list[float]:
    """Normalize values using robust min-max for 20+ samples, otherwise min-max."""
    items = [float(value) for value in values]
    if not items:
        return []
    reference = fit_normalization_reference(items)
    return transform_with_reference(items, reference)


def fit_normalization_reference(values: Iterable[float]) -> NormalizationReference:
    """Fit the same bounds used by :func:`normalize` without transforming values."""
    items = [float(value) for value in values]
    if not items:
        raise ValueError("normalization reference requires at least one value")
    if len(items) >= MIN_SAMPLES_FOR_ROBUST_SCALING:
        lower = percentile(items, NORMALIZATION_LOWER_PERCENTILE)
        upper = percentile(items, NORMALIZATION_UPPER_PERCENTILE)
    else:
        lower, upper = min(items), max(items)
    return NormalizationReference(lower=lower, upper=upper)


def transform_with_reference(
    values: Iterable[float], reference: NormalizationReference
) -> list[float]:
    """Transform values using fitted bounds, clipping to the reference range."""
    return [
        _scale(min(max(float(value), reference.lower), reference.upper), reference.lower, reference.upper)
        for value in values
    ]


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
