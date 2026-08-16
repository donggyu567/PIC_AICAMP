"""Deterministic mock-backed greedy shelter recommendation core."""

from typing import Any, Mapping, Sequence


def recommend_shelters(
    grids: Sequence[Mapping[str, Any]],
    candidates: Sequence[Mapping[str, Any]],
    n_shelters: int,
) -> list[dict[str, Any]]:
    """Recommend up to ``n_shelters`` candidates using marginal blind-spot gain.

    GIS supplies candidate-to-grid coverage. This function deliberately does
    not inspect coordinates or recalculate spatial relationships.
    """
    _validate_n_shelters(n_shelters)
    grid_by_id = _validate_grids(grids)
    prepared_candidates = _validate_candidates(candidates, grid_by_id)
    if n_shelters == 0:
        return []

    remaining_grid_ids = {
        grid_id for grid_id, grid in grid_by_id.items() if grid["blind_spot"] is True
    }
    recommendations: list[dict[str, Any]] = []
    available = list(prepared_candidates)

    while remaining_grid_ids and available and len(recommendations) < n_shelters:
        gains = [
            _marginal_gain(candidate, remaining_grid_ids, grid_by_id)
            for candidate in available
        ]
        effective_gains = [gain for gain in gains if gain[1]]
        if not effective_gains:
            break
        # Max elderly gain, then max need-score gain, then lexical candidate ID.
        candidate, newly_covered_ids, elderly_sum, _need_sum = min(
            effective_gains,
            key=lambda gain: (-gain[2], -gain[3], gain[0]["candidate_id"]),
        )
        recommendations.append(
            {
                "candidate_id": candidate["candidate_id"],
                "recommendation_rank": len(recommendations) + 1,
                "newly_covered_grid_ids": sorted(newly_covered_ids),
                "newly_covered_elderly_population": elderly_sum,
                # TODO: map this to the final Backend recommendation-reason enum.
                "recommendation_reasons": [],
            }
        )
        remaining_grid_ids.difference_update(newly_covered_ids)
        available.remove(candidate)

    return recommendations


def _validate_n_shelters(n_shelters: int) -> None:
    if isinstance(n_shelters, bool) or not isinstance(n_shelters, int) or n_shelters < 0:
        raise ValueError("n_shelters must be an integer greater than or equal to 0")


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
        blind_spot = grid.get("blind_spot")
        if blind_spot not in {True, False, None}:
            raise ValueError("blind_spot must be true, false, or null")
        if blind_spot is True:
            _validate_target_grid(grid)
        grid_by_id[grid_id] = grid
    return grid_by_id


def _validate_target_grid(grid: Mapping[str, Any]) -> None:
    elderly_population = grid.get("elderly_population")
    if isinstance(elderly_population, bool) or not isinstance(elderly_population, int) or elderly_population < 0:
        raise ValueError("blind_spot grid elderly_population must be an integer greater than or equal to 0")
    need_score = grid.get("installation_need_score")
    if isinstance(need_score, bool) or not isinstance(need_score, (int, float)) or not 0 <= need_score <= 100:
        raise ValueError("blind_spot grid installation_need_score must be between 0 and 100")


def _validate_candidates(
    candidates: Sequence[Mapping[str, Any]], grid_by_id: Mapping[str, Mapping[str, Any]]
) -> list[Mapping[str, Any]]:
    prepared: list[Mapping[str, Any]] = []
    candidate_ids: set[str] = set()
    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            raise ValueError("each candidate must be a mapping")
        candidate_id = candidate.get("candidate_id")
        if not isinstance(candidate_id, str) or not candidate_id:
            raise ValueError("candidate_id must be a non-empty string")
        if candidate_id in candidate_ids:
            raise ValueError(f"duplicate candidate_id: {candidate_id}")
        covered_grid_ids = candidate.get("covered_grid_ids")
        if not isinstance(covered_grid_ids, list):
            raise ValueError("covered_grid_ids must be a list")
        if any(not isinstance(grid_id, str) or not grid_id for grid_id in covered_grid_ids):
            raise ValueError("covered_grid_ids must contain non-empty string grid IDs")
        unknown_ids = set(covered_grid_ids) - set(grid_by_id)
        if unknown_ids:
            raise ValueError(f"candidate references unknown grid_id: {sorted(unknown_ids)[0]}")
        candidate_ids.add(candidate_id)
        prepared.append(candidate)
    return prepared


def _marginal_gain(
    candidate: Mapping[str, Any], remaining_grid_ids: set[str], grid_by_id: Mapping[str, Mapping[str, Any]]
) -> tuple[Mapping[str, Any], set[str], int, float]:
    newly_covered_ids = set(candidate["covered_grid_ids"]) & remaining_grid_ids
    elderly_sum = sum(grid_by_id[grid_id]["elderly_population"] for grid_id in newly_covered_ids)
    need_sum = sum(grid_by_id[grid_id]["installation_need_score"] for grid_id in newly_covered_ids)
    return candidate, newly_covered_ids, elderly_sum, need_sum
