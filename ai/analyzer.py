"""Public analysis entry point, independent of file I/O and APIs."""

from typing import Any, Mapping, Sequence

from .config import INSTALLATION_WEIGHTS, VULNERABILITY_WEIGHTS
from .normalization import normalize
from .schemas import validate_grid
from .scoring import main_factors, risk_level, weighted_score

_FEATURE_TO_COMPONENT = {
    "heat_exposure_value": "heat",
    "elderly_ratio": "elderly",
    "farmland_ratio": "farmland",
    "nearest_shelter_distance_m": "coverage_gap",
}


def analyze_grids(grids: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Analyze grids and return JSON-serializable dictionaries.

    Invalid or incomplete grids neither receive a rank nor affect the scaling
    population used by valid grids.
    """
    prepared: list[dict[str, Any]] = []
    valid_indexes: list[int] = []
    for index, source in enumerate(grids):
        grid = dict(source)
        missing, errors = validate_grid(grid)
        result: dict[str, Any] = {
            "grid_id": grid.get("grid_id"),
            "current_covered": grid.get("current_covered"),
            "missing_fields": missing,
        }
        if errors:
            result.update(_empty_result("INVALID_DATA", errors))
        elif missing:
            result.update(_empty_result("INSUFFICIENT_DATA"))
        else:
            result["analysis_status"] = "OK"
            valid_indexes.append(index)
        prepared.append({"grid": grid, "result": result})

    for feature, component in _FEATURE_TO_COMPONENT.items():
        scores = normalize([prepared[index]["grid"][feature] for index in valid_indexes])
        for index, score in zip(valid_indexes, scores):
            prepared[index]["result"][f"{component}_score"] = round(score, 2)

    for index in valid_indexes:
        result = prepared[index]["result"]
        vulnerability_components = {name: result[f"{name}_score"] for name in VULNERABILITY_WEIGHTS}
        vulnerability = weighted_score(vulnerability_components, VULNERABILITY_WEIGHTS)
        components = {**vulnerability_components, "coverage_gap": result["coverage_gap_score"]}
        installation = weighted_score(components, INSTALLATION_WEIGHTS)
        level = risk_level(vulnerability)
        result.update(
            vulnerability_score=round(vulnerability, 2),
            risk_level=level,
            installation_need_score=round(installation, 2),
            installation_rank=None,
            blind_spot=_blind_spot(result["current_covered"], level),
            main_factors=main_factors(components),
        )

    ranked = sorted(
        (prepared[index]["result"] for index in valid_indexes),
        key=lambda result: (-result["installation_need_score"], str(result.get("grid_id") or "")),
    )
    for rank, result in enumerate(ranked, 1):
        result["installation_rank"] = rank
    return [entry["result"] for entry in prepared]


def _empty_result(status: str, validation_errors: list[str] | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "heat_score": None, "elderly_score": None, "farmland_score": None, "coverage_gap_score": None,
        "vulnerability_score": None, "risk_level": None, "installation_need_score": None,
        "installation_rank": None, "blind_spot": None, "main_factors": [], "analysis_status": status,
    }
    if validation_errors:
        result["validation_errors"] = validation_errors
    return result


def _blind_spot(current_covered: Any, level: str) -> bool | None:
    if current_covered is None:
        return None
    return current_covered is False and level in {"HIGH", "VERY_HIGH"}
