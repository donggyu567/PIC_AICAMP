"""Deterministic Alert v0.2 evaluation, independent of storage and APIs."""

from .evaluator import evaluate_alerts
from .schemas import AlertResult

__all__ = ["AlertResult", "evaluate_alerts"]
