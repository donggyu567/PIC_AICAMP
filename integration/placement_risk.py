"""MVP placement-aware residual-risk simulation across AI and GIS domains."""

from __future__ import annotations

from copy import deepcopy
from numbers import Real
from typing import Any, Iterable, Mapping, Sequence

import pandas as pd

from ai.config import INSTALLATION_WEIGHTS
from ai.coverage import calculate_coverage_comparison
from ai.normalization import (
    NormalizationReference,
    fit_normalization_reference,
    transform_with_reference,
)
from ai.scoring import blind_spot, placement_risk_level, weighted_score
from gis.placement_accessibility import calculate_accessibility_with_placements
from gis.placement_coverage import validate_placements


_ACCESS_FIELDS = {
    "grid_id",
    "nearest_shelter_distance_m",
    "shelter_count",
    "current_covered",
}


def simulate_placement_risk(
    grid_features: pd.DataFrame,
    baseline_analysis: Sequence[Mapping[str, Any]],
    baseline_accessibility: pd.DataFrame,
    existing_shelters: pd.DataFrame,
    placements: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Return per-grid before/after accessibility and placement-risk results.

    Structural ``vulnerability_score`` and ``risk_level`` are copied unchanged
    to both states. Only the fixed-baseline accessibility component changes the
    separate MVP v0.1 ``placement_risk_score``.
    """
    grids = grid_features.copy(deep=True)
    accessibility = baseline_accessibility.copy(deep=True)
    shelter_source = existing_shelters.copy(deep=True)
    analysis_source = deepcopy(list(baseline_analysis))
    placement_records = validate_placements(placements)

    grid_by_id = _index_grid_frame(grids)
    access_by_id = _index_accessibility(accessibility)
    analysis_by_id = _index_analysis(analysis_source)
    _require_same_grid_ids(grid_by_id, access_by_id, analysis_by_id)

    valid_grid_ids = [
        grid_id
        for grid_id, result in analysis_by_id.items()
        if result.get("analysis_status") == "OK"
    ]
    _validate_baseline_accessibility(valid_grid_ids, access_by_id)
    baseline_distances = [
        _required_number(
            access_by_id[grid_id].get("nearest_shelter_distance_m"),
            "nearest_shelter_distance_m",
        )
        for grid_id in valid_grid_ids
    ]
    reference = (
        fit_normalization_reference(baseline_distances)
        if baseline_distances
        else None
    )
    _validate_baseline_coverage_scores(valid_grid_ids, analysis_by_id, access_by_id, reference)

    after_accessibility = (
        accessibility.copy(deep=True)
        if not placement_records
        else calculate_accessibility_with_placements(grids, shelter_source, placement_records)
    )
    after_by_id = _index_accessibility(after_accessibility)
    if set(after_by_id) != set(grid_by_id):
        raise ValueError("after accessibility grid_ids must match the grid cohort")

    grid_results: list[dict[str, Any]] = []
    coverage_grids: list[dict[str, Any]] = []
    for grid_id in sorted(grid_by_id):
        grid = grid_by_id[grid_id]
        analysis = analysis_by_id[grid_id]
        before_access = access_by_id[grid_id]
        after_access = after_by_id[grid_id]
        before_state = _state(analysis, before_access, reference)
        after_state = _state(analysis, after_access, reference)
        _validate_accessibility_monotonicity(grid_id, before_state, after_state)

        newly_covered = (
            before_state["current_covered"] is False
            and after_state["current_covered"] is True
        )
        grid_results.append(
            {
                "grid_id": grid_id,
                "before": before_state,
                "after": after_state,
                "newly_covered": newly_covered,
            }
        )
        coverage_grid = {
            **grid,
            **analysis,
            "current_covered": before_state["current_covered"],
            "blind_spot": before_state["blind_spot"],
        }
        elderly_population = _optional_number(coverage_grid.get("elderly_population"))
        if elderly_population is not None and elderly_population.is_integer():
            coverage_grid["elderly_population"] = int(elderly_population)
        coverage_grids.append(coverage_grid)

    newly_covered_grid_ids = [
        result["grid_id"] for result in grid_results if result["newly_covered"]
    ]
    vulnerable_newly_covered_ids = [
        result["grid_id"]
        for result in grid_results
        if result["newly_covered"] and result["before"]["blind_spot"] is True
    ]
    coverage = calculate_coverage_comparison(
        coverage_grids,
        [{"newly_covered_grid_ids": vulnerable_newly_covered_ids}],
    )
    improvement = coverage["improvement"]
    return {
        "requested_shelter_count": len(placement_records),
        "selected_placement_ids": [record["placement_id"] for record in placement_records],
        "newly_covered_grid_ids": newly_covered_grid_ids,
        "newly_covered_elderly_population": improvement["newly_covered_vulnerable_population"],
        "reduced_blind_spot_count": improvement["blind_spot_grid_reduction_count"],
        "coverage_ratio_change": improvement["vulnerable_population_coverage_rate_delta"],
        "coverage_comparison": coverage,
        "grid_results": grid_results,
    }


def _state(
    analysis: Mapping[str, Any],
    accessibility: Mapping[str, Any],
    reference: NormalizationReference | None,
) -> dict[str, Any]:
    distance = _optional_number(accessibility.get("nearest_shelter_distance_m"))
    count = _optional_integer(accessibility.get("shelter_count"))
    covered = _optional_bool(accessibility.get("current_covered"))
    vulnerability = _optional_number(analysis.get("vulnerability_score"))
    structural_level = _optional_string(analysis.get("risk_level"), "risk_level")

    placement_score: float | None = None
    if analysis.get("analysis_status") == "OK":
        if distance is None or reference is None:
            raise ValueError("valid analysis requires distance and normalization reference")
        placement_score = _calculate_placement_risk_score(analysis, distance, reference)

    return {
        "nearest_shelter_distance_m": distance,
        "shelter_count": count,
        "current_covered": covered,
        "blind_spot": blind_spot(covered, structural_level),
        "vulnerability_score": vulnerability,
        "risk_level": structural_level,
        "placement_risk_score": placement_score,
        "placement_risk_level": (
            None if placement_score is None else placement_risk_level(placement_score)
        ),
    }


def _calculate_placement_risk_score(
    analysis: Mapping[str, Any],
    distance: float,
    reference: NormalizationReference,
) -> float:
    """Calculate the scenario score independently from installation_need_score."""
    coverage_gap_score = round(transform_with_reference([distance], reference)[0], 2)
    components = {
        name: _required_number(analysis.get(f"{name}_score"), f"{name}_score")
        for name in ("heat", "elderly", "farmland")
    }
    return round(
        weighted_score(
            {**components, "coverage_gap": coverage_gap_score},
            INSTALLATION_WEIGHTS,
        ),
        2,
    )


def _index_grid_frame(data: pd.DataFrame) -> dict[str, dict[str, Any]]:
    required = {"grid_id", "centroid_x", "centroid_y"}
    if not required.issubset(data.columns):
        raise ValueError("grid features are missing required fields")
    return _index_records(data.to_dict("records"), "grid features")


def _index_accessibility(data: pd.DataFrame) -> dict[str, dict[str, Any]]:
    if not _ACCESS_FIELDS.issubset(data.columns):
        raise ValueError("accessibility data is missing required fields")
    return _index_records(data.to_dict("records"), "accessibility")


def _index_analysis(data: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    return _index_records(data, "analysis")


def _index_records(
    records: Iterable[Mapping[str, Any]], source: str
) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, Mapping):
            raise ValueError(f"each {source} row must be a mapping")
        grid_id = record.get("grid_id")
        if not isinstance(grid_id, str) or not grid_id:
            raise ValueError(f"{source} grid_id must be a non-empty string")
        if grid_id in indexed:
            raise ValueError(f"duplicate {source} grid_id: {grid_id}")
        indexed[grid_id] = dict(record)
    return indexed


def _require_same_grid_ids(*indexes: Mapping[str, Any]) -> None:
    expected = set(indexes[0])
    if any(set(index) != expected for index in indexes[1:]):
        raise ValueError("grid, accessibility, and analysis grid_ids must match")


def _validate_baseline_coverage_scores(
    valid_grid_ids: Sequence[str],
    analysis_by_id: Mapping[str, Mapping[str, Any]],
    access_by_id: Mapping[str, Mapping[str, Any]],
    reference: NormalizationReference | None,
) -> None:
    if not valid_grid_ids:
        return
    if reference is None:
        raise ValueError("valid analysis requires a normalization reference")
    distances = [
        _required_number(access_by_id[grid_id].get("nearest_shelter_distance_m"), "nearest_shelter_distance_m")
        for grid_id in valid_grid_ids
    ]
    expected_scores = transform_with_reference(distances, reference)
    for grid_id, expected in zip(valid_grid_ids, expected_scores):
        actual = _required_number(
            analysis_by_id[grid_id].get("coverage_gap_score"), "coverage_gap_score"
        )
        if abs(actual - round(expected, 2)) > 0.011:
            raise ValueError(
                f"baseline coverage_gap_score does not match accessibility for grid_id: {grid_id}"
            )


def _validate_baseline_accessibility(
    valid_grid_ids: Sequence[str],
    access_by_id: Mapping[str, Mapping[str, Any]],
) -> None:
    """Require complete baseline access for every normally analyzed grid."""
    validators = {
        "nearest_shelter_distance_m": _optional_number,
        "shelter_count": _optional_integer,
        "current_covered": _optional_bool,
    }
    for grid_id in valid_grid_ids:
        accessibility = access_by_id[grid_id]
        for field, validator in validators.items():
            try:
                value = validator(accessibility.get(field))
            except ValueError as exc:
                raise ValueError(
                    f"baseline accessibility field '{field}' is invalid for grid_id: {grid_id}"
                ) from exc
            if value is None:
                raise ValueError(
                    f"baseline accessibility field '{field}' is missing for grid_id: {grid_id}"
                )


def _validate_accessibility_monotonicity(
    grid_id: str, before: Mapping[str, Any], after: Mapping[str, Any]
) -> None:
    before_distance = before["nearest_shelter_distance_m"]
    after_distance = after["nearest_shelter_distance_m"]
    if before_distance is not None and after_distance is not None and after_distance > before_distance + 1e-6:
        raise ValueError(f"placement increased nearest shelter distance for grid_id: {grid_id}")
    before_count = before["shelter_count"]
    after_count = after["shelter_count"]
    if before_count is not None and after_count is not None and after_count < before_count:
        raise ValueError(f"placement reduced shelter_count for grid_id: {grid_id}")
    before_score = before["placement_risk_score"]
    after_score = after["placement_risk_score"]
    if before_score is not None and after_score is not None and after_score > before_score + 0.011:
        raise ValueError(f"placement increased placement risk for grid_id: {grid_id}")


def _optional_number(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError("numeric result must be a number or null")
    return float(value)


def _required_number(value: Any, field: str) -> float:
    result = _optional_number(value)
    if result is None:
        raise ValueError(f"{field} must be numeric for valid analysis")
    return result


def _optional_integer(value: Any) -> int | None:
    number = _optional_number(value)
    if number is None:
        return None
    if not number.is_integer() or number < 0:
        raise ValueError("shelter_count must be a non-negative integer or null")
    return int(number)


def _optional_bool(value: Any) -> bool | None:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, bool) or value.__class__.__name__ == "bool_":
        return bool(value)
    raise ValueError("current_covered must be boolean or null")


def _optional_string(value: Any, field: str) -> str | None:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, str):
        return value
    raise ValueError(f"{field} must be a string or null")
