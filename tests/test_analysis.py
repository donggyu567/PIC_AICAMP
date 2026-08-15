import json
from pathlib import Path

import pytest

from ai.analyzer import analyze_grids
from ai.normalization import normalize
from ai.scoring import risk_level


def grid(grid_id="G001", **changes):
    value = {
        "grid_id": grid_id, "heat_exposure_value": 35.0, "elderly_ratio": 0.4,
        "farmland_ratio": 0.5, "nearest_shelter_distance_m": 1000.0,
        "population": 100, "elderly_population": 40, "current_covered": False,
        "grid_area_m2": 250000,
    }
    value.update(changes)
    return value


def test_component_scores_and_weighted_scores_are_in_range_and_consistent():
    results = analyze_grids([grid("G001", heat_exposure_value=20), grid("G002", heat_exposure_value=40)])
    for result in results:
        for field in ("heat_score", "elderly_score", "farmland_score", "coverage_gap_score", "vulnerability_score", "installation_need_score"):
            assert 0 <= result[field] <= 100
        assert result["installation_need_score"] == pytest.approx(
            0.75 * result["vulnerability_score"] + 0.25 * result["coverage_gap_score"], abs=0.02
        )


@pytest.mark.parametrize("score,expected", [(24.999, "LOW"), (25, "MODERATE"), (49.999, "MODERATE"), (50, "HIGH"), (74.999, "HIGH"), (75, "VERY_HIGH"), (100, "VERY_HIGH")])
def test_risk_level_boundaries(score, expected):
    assert risk_level(score) == expected


def test_blind_spot_and_null_coverage_handling():
    high = grid("HIGH", heat_exposure_value=100, elderly_ratio=1, farmland_ratio=1, nearest_shelter_distance_m=1000)
    low = grid("LOW", heat_exposure_value=0, elderly_ratio=0, farmland_ratio=0, nearest_shelter_distance_m=0)
    results = {item["grid_id"]: item for item in analyze_grids([high, low])}
    assert results["HIGH"]["risk_level"] == "VERY_HIGH"
    assert results["HIGH"]["blind_spot"] is True
    covered = analyze_grids([high | {"current_covered": True}, low])[0]
    unknown = analyze_grids([high | {"current_covered": None}, low])[0]
    assert covered["blind_spot"] is False
    assert unknown["blind_spot"] is None


@pytest.mark.parametrize("changes", [
    {"heat_exposure_value": None}, {"elderly_ratio": 1.4}, {"farmland_ratio": -0.1}, {"nearest_shelter_distance_m": -1},
])
def test_incomplete_and_invalid_data_are_distinguished(changes):
    result = analyze_grids([grid(**changes)])[0]
    expected = "INSUFFICIENT_DATA" if changes.get("heat_exposure_value", 1) is None else "INVALID_DATA"
    assert result["analysis_status"] == expected
    assert result["installation_rank"] is None
    assert result["vulnerability_score"] is None


def test_equal_values_normalize_to_fifty():
    assert normalize([3, 3, 3]) == [50.0, 50.0, 50.0]
    results = analyze_grids([grid("A"), grid("B")])
    assert all(result["heat_score"] == 50 for result in results)


def test_ranking_and_tie_break_are_deterministic():
    a = grid("A", heat_exposure_value=1, elderly_ratio=0, farmland_ratio=0, nearest_shelter_distance_m=0)
    b = grid("B", heat_exposure_value=1, elderly_ratio=0, farmland_ratio=0, nearest_shelter_distance_m=0)
    high = grid("Z", heat_exposure_value=2, elderly_ratio=1, farmland_ratio=1, nearest_shelter_distance_m=1)
    first = analyze_grids([b, high, a])
    second = analyze_grids([b, high, a])
    ranks = {item["grid_id"]: item["installation_rank"] for item in first}
    assert ranks["Z"] == 1 and ranks["A"] < ranks["B"]
    assert first == second


def test_main_factors_descend_by_score_and_exclude_below_threshold():
    high = grid("HIGH", heat_exposure_value=100, elderly_ratio=0.8, farmland_ratio=0.6, nearest_shelter_distance_m=1000)
    low = grid("LOW", heat_exposure_value=0, elderly_ratio=0, farmland_ratio=0, nearest_shelter_distance_m=0)
    result = analyze_grids([high, low])[0]
    assert result["main_factors"] == ["HIGH_HEAT", "HIGH_ELDERLY_RATIO", "HIGH_FARMLAND_RATIO"]


def test_mock_data_is_deterministic_and_has_25_records():
    grids = json.loads((Path("mocks") / "grids.json").read_text(encoding="utf-8"))
    assert len(grids) == 25
    assert analyze_grids(grids) == analyze_grids(grids)
