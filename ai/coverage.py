"""Before/after vulnerable-population coverage comparison."""

from typing import Any, Mapping, Sequence


def calculate_coverage_comparison(
    grids: Sequence[Mapping[str, Any]], recommendations: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    """Calculate coverage effects from analysis grids and Greedy output only.

    The function deliberately consumes ``newly_covered_grid_ids`` rather than
    candidate coordinates or candidate coverage, so no GIS calculation is
    repeated here.
    """
    grid_by_id = _validate_grids(grids)
    vulnerable_ids = {grid_id for grid_id, grid in grid_by_id.items() if _is_vulnerable(grid)}
    blind_spot_ids = {grid_id for grid_id, grid in grid_by_id.items() if grid["blind_spot"] is True}
    newly_covered_ids = _validate_recommendations(recommendations, grid_by_id, vulnerable_ids)

    total_population = sum(grid_by_id[grid_id]["elderly_population"] for grid_id in vulnerable_ids)
    before_covered_ids = {
        grid_id for grid_id in vulnerable_ids if grid_by_id[grid_id]["current_covered"] is True
    }
    after_covered_ids = before_covered_ids | newly_covered_ids
    before_covered_population = sum(grid_by_id[grid_id]["elderly_population"] for grid_id in before_covered_ids)
    after_covered_population = sum(grid_by_id[grid_id]["elderly_population"] for grid_id in after_covered_ids)

    before_rate = _coverage_rate(before_covered_population, total_population)
    after_rate = _coverage_rate(after_covered_population, total_population)
    before_area = _blind_spot_area(blind_spot_ids, grid_by_id)
    remaining_blind_spot_ids = blind_spot_ids - newly_covered_ids
    after_area = _blind_spot_area(remaining_blind_spot_ids, grid_by_id) if before_area is not None else None

    return {
        "total_vulnerable_population": total_population,
        "before": {
            "covered_vulnerable_population": before_covered_population,
            "vulnerable_population_coverage_rate": before_rate,
            "blind_spot_grid_count": len(blind_spot_ids),
            "blind_spot_area_m2": before_area,
        },
        "after": {
            "covered_vulnerable_population": after_covered_population,
            "vulnerable_population_coverage_rate": after_rate,
            "blind_spot_grid_count": len(remaining_blind_spot_ids),
            "blind_spot_area_m2": after_area,
        },
        "improvement": {
            "newly_covered_vulnerable_population": after_covered_population - before_covered_population,
            "vulnerable_population_coverage_rate_delta": None if before_rate is None else round(after_rate - before_rate, 12),
            "blind_spot_grid_reduction_count": len(blind_spot_ids) - len(remaining_blind_spot_ids),
        },
    }


def _validate_grids(grids: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    grid_by_id: dict[str, Mapping[str, Any]] = {}
    for grid in grids:
        if not isinstance(grid, Mapping):
            raise ValueError("each grid must be a mapping")
        grid_id = grid.get("grid_id")
        if not isinstance(grid_id, str) or not grid_id:
            raise ValueError("grid_id must be a non-empty string")
        if grid_id in grid_by_id:
            raise ValueError(f"duplicate grid_id: {grid_id}")
        current_covered = grid.get("current_covered")
        if current_covered is not True and current_covered is not False and current_covered is not None:
            raise ValueError("current_covered must be true, false, or null")
        blind_spot = grid.get("blind_spot")
        if blind_spot is not True and blind_spot is not False and blind_spot is not None:
            raise ValueError("blind_spot must be true, false, or null")
        if _is_vulnerable(grid):
            _validate_elderly_population(grid)
        grid_by_id[grid_id] = grid
    return grid_by_id


def _is_vulnerable(grid: Mapping[str, Any]) -> bool:
    return (
        grid.get("analysis_status") == "OK"
        and grid.get("risk_level") in {"HIGH", "VERY_HIGH"}
        and grid.get("current_covered") is not None
    )


def _validate_elderly_population(grid: Mapping[str, Any]) -> None:
    value = grid.get("elderly_population")
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("vulnerable grid elderly_population must be an integer greater than or equal to 0")


def _validate_recommendations(
    recommendations: Sequence[Mapping[str, Any]],
    grid_by_id: Mapping[str, Mapping[str, Any]],
    vulnerable_ids: set[str],
) -> set[str]:
    newly_covered_ids: set[str] = set()
    for recommendation in recommendations:
        if not isinstance(recommendation, Mapping):
            raise ValueError("each recommendation must be a mapping")
        covered_ids = recommendation.get("newly_covered_grid_ids")
        if not isinstance(covered_ids, list):
            raise ValueError("newly_covered_grid_ids must be a list")
        for grid_id in covered_ids:
            if not isinstance(grid_id, str) or not grid_id:
                raise ValueError("newly_covered_grid_ids must contain non-empty string grid IDs")
            if grid_id not in grid_by_id:
                raise ValueError(f"recommendation references unknown grid_id: {grid_id}")
            if grid_by_id[grid_id]["blind_spot"] is not True or grid_id not in vulnerable_ids:
                raise ValueError(f"recommendation grid_id is not a vulnerable blind_spot: {grid_id}")
            newly_covered_ids.add(grid_id)
    return newly_covered_ids


def _coverage_rate(covered_population: int, total_population: int) -> float | None:
    if total_population == 0:
        return None
    return covered_population / total_population


def _blind_spot_area(
    blind_spot_ids: set[str], grid_by_id: Mapping[str, Mapping[str, Any]]
) -> float | int | None:
    areas: list[float | int] = []
    for grid_id in blind_spot_ids:
        area = grid_by_id[grid_id].get("grid_area_m2")
        if area is None:
            return None
        if isinstance(area, bool) or not isinstance(area, (int, float)) or area < 0:
            raise ValueError("blind_spot grid_area_m2 must be a non-negative number when provided")
        areas.append(area)
    return sum(areas)
