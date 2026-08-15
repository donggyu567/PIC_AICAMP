"""Input validation helpers for dictionary-based grid data."""

from typing import Any, Mapping

from .config import REQUIRED_FEATURES


def validate_grid(grid: Mapping[str, Any]) -> tuple[list[str], list[str]]:
    """Return ``(missing_required_fields, validation_errors)`` for a grid."""
    missing = [field for field in REQUIRED_FEATURES if grid.get(field) is None]
    errors: list[str] = []

    for field in (*REQUIRED_FEATURES, "population", "elderly_population", "grid_area_m2"):
        value = grid.get(field)
        if value is not None and not _number(value):
            errors.append(f"{field} must be numeric")
    _check_range(grid, "elderly_ratio", 0, 1, errors)
    _check_range(grid, "farmland_ratio", 0, 1, errors)
    _check_minimum(grid, "nearest_shelter_distance_m", 0, errors)
    _check_minimum(grid, "population", 0, errors)
    _check_minimum(grid, "elderly_population", 0, errors)
    if grid.get("grid_area_m2") is not None:
        _check_minimum(grid, "grid_area_m2", 0, errors, strictly_greater=True)
    return missing, errors


def _number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _check_range(grid: Mapping[str, Any], field: str, low: float, high: float, errors: list[str]) -> None:
    value = grid.get(field)
    if value is not None and _number(value) and (value < low or value > high):
        errors.append(f"{field} must be between {low} and {high}")


def _check_minimum(
    grid: Mapping[str, Any], field: str, minimum: float, errors: list[str], *, strictly_greater: bool = False
) -> None:
    value = grid.get(field)
    if value is None:
        return
    invalid = _number(value) and (value <= minimum if strictly_greater else value < minimum)
    if invalid:
        operator = ">" if strictly_greater else ">="
        errors.append(f"{field} must be {operator} {minimum}")
