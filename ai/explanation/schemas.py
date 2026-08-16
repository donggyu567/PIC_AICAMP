"""Contracts for LLM-safe, read-only recommendation explanations."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class CoveredGrid:
    grid_id: str
    region_name: str | None
    installation_need_score: float | None
    risk_level: str | None
    elderly_ratio: float | None
    farmland_ratio: float | None
    nearest_shelter_distance_m: float | None
    main_factors: tuple[str, ...]


@dataclass(frozen=True)
class ExplanationInput:
    """Minimal facts an LLM may use for one already-ranked candidate."""

    candidate_id: str
    candidate_name: str
    candidate_type: str | None
    recommendation_rank: int
    newly_covered_grid_count: int
    newly_covered_elderly_population: int
    covered_grids: tuple[CoveredGrid, ...]
    before: Mapping[str, Any]
    after: Mapping[str, Any]
    overall_improvement: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["covered_grids"] = [asdict(grid) for grid in self.covered_grids]
        return data


@dataclass(frozen=True)
class ExplanationOutput:
    candidate_id: str
    summary: str
    key_reasons: tuple[str, ...]
    expected_effect: str
    decision_note: str

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["key_reasons"] = list(self.key_reasons)
        return data


def build_explanation_input(
    recommendation: Mapping[str, Any],
    candidate: Mapping[str, Any],
    grids_by_id: Mapping[str, Mapping[str, Any]],
    coverage: Mapping[str, Any],
) -> ExplanationInput:
    """Build a non-mutating explanation payload from existing AI/GIS outputs.

    Candidate details and coverage facts are passed through only when provided;
    this function deliberately does not infer missing facts.
    """
    candidate_id = _required_string(recommendation, "candidate_id")
    if candidate.get("candidate_id") != candidate_id:
        raise ValueError("candidate_id does not match recommendation")
    grid_ids = recommendation.get("newly_covered_grid_ids")
    if not isinstance(grid_ids, list) or any(not isinstance(value, str) or not value for value in grid_ids):
        raise ValueError("newly_covered_grid_ids must be a list of non-empty strings")
    if len(set(grid_ids)) != len(grid_ids):
        raise ValueError("newly_covered_grid_ids must not contain duplicates")
    covered_grids = tuple(_covered_grid(grid_id, grids_by_id) for grid_id in grid_ids)
    population = recommendation.get("newly_covered_elderly_population")
    if isinstance(population, bool) or not isinstance(population, int) or population < 0:
        raise ValueError("newly_covered_elderly_population must be a non-negative integer")
    rank = recommendation.get("recommendation_rank")
    if isinstance(rank, bool) or not isinstance(rank, int) or rank < 1:
        raise ValueError("recommendation_rank must be a positive integer")
    return ExplanationInput(
        candidate_id=candidate_id,
        candidate_name=_required_string(candidate, "candidate_name"),
        candidate_type=_optional_string(candidate.get("candidate_type")),
        recommendation_rank=rank,
        newly_covered_grid_count=len(grid_ids),
        newly_covered_elderly_population=population,
        covered_grids=covered_grids,
        before=_coverage_part(coverage, "before"),
        after=_coverage_part(coverage, "after"),
        overall_improvement=_coverage_part(coverage, "improvement"),
    )


def _covered_grid(grid_id: str, grids_by_id: Mapping[str, Mapping[str, Any]]) -> CoveredGrid:
    if grid_id not in grids_by_id:
        raise ValueError(f"recommendation references unknown grid_id: {grid_id}")
    grid = grids_by_id[grid_id]
    factors = grid.get("main_factors", [])
    if not isinstance(factors, list) or any(not isinstance(value, str) for value in factors):
        raise ValueError("main_factors must be a list of strings")
    return CoveredGrid(
        grid_id=grid_id,
        region_name=_optional_string(grid.get("region_name")),
        installation_need_score=_optional_number(grid.get("installation_need_score")),
        risk_level=_optional_string(grid.get("risk_level")),
        elderly_ratio=_optional_number(grid.get("elderly_ratio")),
        farmland_ratio=_optional_number(grid.get("farmland_ratio")),
        nearest_shelter_distance_m=_optional_number(grid.get("nearest_shelter_distance_m")),
        main_factors=tuple(factors),
    )


def _coverage_part(coverage: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    value = coverage.get(name)
    if not isinstance(value, Mapping):
        raise ValueError(f"coverage.{name} must be a mapping")
    return dict(value)


def _required_string(data: Mapping[str, Any], name: str) -> str:
    value = data.get(name)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _optional_string(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _optional_number(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("optional numeric value must be a number")
    return float(value)
