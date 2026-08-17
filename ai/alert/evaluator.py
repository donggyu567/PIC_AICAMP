"""Pure deterministic evaluator for the frozen Alert v0.2 rules."""

from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

from .config import (
    ALERT_HIGH_INSTALLATION_NEED_THRESHOLD,
    ALERT_INSTALLATION_NEED_DELTA,
    ALERT_LOW_ACCESSIBILITY_SCORE_THRESHOLD,
    ALERT_TOP_PRIORITY_RATIO,
    RISK_LEVEL_ORDER,
)
from .schemas import AlertResult


def evaluate_alerts(
    current_grids: Sequence[Mapping[str, Any]],
    previous_grids: Sequence[Mapping[str, Any]] | None = None,
    *,
    current_heatwave_warning_active: bool = False,
    previous_heatwave_warning_active: bool = False,
) -> list[dict[str, Any]]:
    """Evaluate frozen Alert v0.2 rules without mutating analysis results.

    A grid is decisionable only when its analysis is ``OK`` and its
    ``current_covered`` value is known.  Priority uses the batch-wide top
    ``ceil(valid_count * 0.20)`` installation-need ranks, breaking score ties
    by ascending ``grid_id``.  Initial observations emit WATCH rather than a
    synthetic change event; re-analysis emits only genuine changes.
    """
    current = _index_grids(current_grids, "current")
    previous = _index_grids(previous_grids, "previous") if previous_grids is not None else {}
    top_priority_ids = _top_priority_ids(current)
    warning_started = (previous_heatwave_warning_active is not True and current_heatwave_warning_active is True)
    results: list[dict[str, Any]] = []

    for grid in current.values():
        grid_id = grid["grid_id"]
        if not _decisionable(grid):
            results.append(_undecidable(grid_id, grid.get("risk_level")))
            continue
        reasons = _priority_reasons(grid, top_priority_ids)
        if current_heatwave_warning_active is True:
            reasons.append("HEATWAVE_WARNING_ACTIVE")
        if grid.get("blind_spot") is not True:
            results.append(_result(grid_id, False, "NONE", reasons, [], None, None, grid.get("risk_level")))
            continue

        prior = previous.get(grid_id)
        initial = prior is None or not _decisionable(prior)
        events: list[str] = []
        delta: float | None = None
        previous_risk = prior.get("risk_level") if prior is not None else None
        if initial:
            # No previous snapshot is not a fabricated previous score or event.
            if reasons:
                reasons.append("NEW_BLIND_SPOT")
                results.append(_result(grid_id, True, "WATCH", reasons, events, None, previous_risk, grid.get("risk_level")))
            else:
                results.append(_result(grid_id, False, "NONE", reasons, events, None, previous_risk, grid.get("risk_level")))
            continue

        if prior.get("blind_spot") is not True:
            events.append("NEW_BLIND_SPOT")
        delta = _installation_need_delta(grid, prior)
        if delta is not None and delta >= ALERT_INSTALLATION_NEED_DELTA:
            events.append("INSTALLATION_NEED_INCREASED")
        if _risk_increased(previous_risk, grid.get("risk_level")):
            events.append("RISK_LEVEL_INCREASED")
        if warning_started:
            events.append("HEATWAVE_WARNING_STARTED")
        reasons.extend(events)

        priority = bool(_priority_reasons(grid, top_priority_ids))
        if not priority:
            results.append(_result(grid_id, False, "NONE", reasons, events, delta, previous_risk, grid.get("risk_level")))
        elif "HEATWAVE_WARNING_STARTED" in events:
            results.append(_result(grid_id, True, "URGENT", reasons, events, delta, previous_risk, grid.get("risk_level")))
        elif events:
            results.append(_result(grid_id, True, "WARNING", reasons, events, delta, previous_risk, grid.get("risk_level")))
        else:
            results.append(_result(grid_id, False, "NONE", reasons, events, delta, previous_risk, grid.get("risk_level")))
    return results


def _index_grids(grids: Sequence[Mapping[str, Any]], label: str) -> dict[str, Mapping[str, Any]]:
    if not isinstance(grids, Sequence) or isinstance(grids, (str, bytes)):
        raise ValueError(f"{label}_grids must be a sequence of mappings")
    indexed: dict[str, Mapping[str, Any]] = {}
    for grid in grids:
        if not isinstance(grid, Mapping):
            raise ValueError(f"each {label} grid must be a mapping")
        grid_id = grid.get("grid_id")
        if not isinstance(grid_id, str) or not grid_id:
            raise ValueError("grid_id must be a non-empty string")
        if grid_id in indexed:
            raise ValueError(f"duplicate {label} grid_id: {grid_id}")
        indexed[grid_id] = grid
    return indexed


def _decisionable(grid: Mapping[str, Any]) -> bool:
    return grid.get("analysis_status") == "OK" and grid.get("current_covered") in {True, False}


def _top_priority_ids(grids: Mapping[str, Mapping[str, Any]]) -> set[str]:
    valid = [
        grid for grid in grids.values()
        if grid.get("analysis_status") == "OK" and _number(grid.get("installation_need_score")) is not None
    ]
    count = math.ceil(len(valid) * ALERT_TOP_PRIORITY_RATIO)
    ranked = sorted(valid, key=lambda grid: (-_number(grid["installation_need_score"]), grid["grid_id"]))
    return {grid["grid_id"] for grid in ranked[:count]}


def _priority_reasons(grid: Mapping[str, Any], top_priority_ids: set[str]) -> list[str]:
    if grid.get("blind_spot") is not True:
        return []
    reasons: list[str] = []
    need = _number(grid.get("installation_need_score"))
    gap = _number(grid.get("coverage_gap_score"))
    if need is not None and need >= ALERT_HIGH_INSTALLATION_NEED_THRESHOLD:
        reasons.append("HIGH_INSTALLATION_NEED")
    if grid["grid_id"] in top_priority_ids:
        reasons.append("TOP_PRIORITY_RANK")
    if gap is not None and gap >= ALERT_LOW_ACCESSIBILITY_SCORE_THRESHOLD:
        reasons.append("LOW_SHELTER_ACCESSIBILITY")
    return reasons


def _installation_need_delta(current: Mapping[str, Any], previous: Mapping[str, Any]) -> float | None:
    now = _number(current.get("installation_need_score"))
    before = _number(previous.get("installation_need_score"))
    return None if now is None or before is None else round(now - before, 12)


def _risk_increased(previous: Any, current: Any) -> bool:
    return previous in RISK_LEVEL_ORDER and current in RISK_LEVEL_ORDER and RISK_LEVEL_ORDER[current] > RISK_LEVEL_ORDER[previous]


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    numeric = float(value)
    return numeric if math.isfinite(numeric) else None


def _undecidable(grid_id: str, risk_level: Any) -> dict[str, Any]:
    return _result(grid_id, None, None, [], [], None, None, risk_level)


def _result(
    grid_id: str, required: bool | None, level: str | None, reasons: list[str], events: list[str],
    delta: float | None, previous_risk: Any, current_risk: Any,
) -> dict[str, Any]:
    return AlertResult(
        grid_id=grid_id,
        alert_required=required,
        alert_level=level,
        alert_reason_codes=tuple(dict.fromkeys(reasons)),
        alert_event_types=tuple(events),
        installation_need_delta=delta,
        previous_risk_level=previous_risk if isinstance(previous_risk, str) else None,
        current_risk_level=current_risk if isinstance(current_risk, str) else None,
    ).to_dict()
