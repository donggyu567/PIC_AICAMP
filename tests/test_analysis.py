import json
from pathlib import Path

import pytest

from ai.analyzer import analyze_grids
from ai.features import calculate_heat_exposure_value
from ai.normalization import normalize
from ai.scoring import risk_level


def grid(grid_id="G001", **changes):
    value = {
        "grid_id": grid_id, "temperature": 35.0, "humidity": 60.0,
        "elderly_ratio": 0.4, "farmland_ratio": 0.5,
        "nearest_shelter_distance_m": 1000.0, "population": 100,
        "elderly_population": 40, "current_covered": False, "grid_area_m2": 250000,
    }
    value.update(changes)
    return value


def test_heat_exposure_uses_kma_stull_formula():
    assert calculate_heat_exposure_value(30.0, 60.0) == pytest.approx(30.4440767985)


@pytest.mark.parametrize("humidity", [0, 100])
def test_humidity_boundary_values_are_valid(humidity):
    assert analyze_grids([grid(humidity=humidity)])[0]["analysis_status"] == "OK"


@pytest.mark.parametrize("field", ["temperature", "humidity"])
def test_missing_weather_input_is_insufficient_data(field):
    result = analyze_grids([grid(**{field: None})])[0]
    assert result["analysis_status"] == "INSUFFICIENT_DATA"
    assert result["missing_fields"] == [field]
    assert result["vulnerability_score"] is None


@pytest.mark.parametrize("humidity", [-1, 101])
def test_out_of_range_humidity_is_invalid(humidity):
    result = analyze_grids([grid(humidity=humidity)])[0]
    assert result["analysis_status"] == "INVALID_DATA"
    assert "humidity" in result["validation_errors"][0]


def test_heat_exposure_is_deterministic():
    assert calculate_heat_exposure_value(33.2, 71.5) == calculate_heat_exposure_value(33.2, 71.5)


def test_component_scores_and_weighted_scores_are_in_range_and_consistent():
    results = analyze_grids([grid("G001", temperature=20), grid("G002", temperature=40)])
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
    high = grid("HIGH", temperature=100, elderly_ratio=1, farmland_ratio=1, nearest_shelter_distance_m=1000)
    low = grid("LOW", temperature=0, elderly_ratio=0, farmland_ratio=0, nearest_shelter_distance_m=0)
    results = {item["grid_id"]: item for item in analyze_grids([high, low])}
    assert results["HIGH"]["risk_level"] == "VERY_HIGH"
    assert results["HIGH"]["blind_spot"] is True
    assert analyze_grids([high | {"current_covered": True}, low])[0]["blind_spot"] is False
    assert analyze_grids([high | {"current_covered": None}, low])[0]["blind_spot"] is None


@pytest.mark.parametrize("changes", [
    {"temperature": None}, {"elderly_ratio": 1.4}, {"farmland_ratio": -0.1}, {"nearest_shelter_distance_m": -1},
])
def test_incomplete_and_invalid_data_are_distinguished(changes):
    result = analyze_grids([grid(**changes)])[0]
    expected = "INSUFFICIENT_DATA" if changes.get("temperature", 1) is None else "INVALID_DATA"
    assert result["analysis_status"] == expected
    assert result["installation_rank"] is None
    assert result["vulnerability_score"] is None


def test_equal_values_normalize_to_fifty():
    assert normalize([3, 3, 3]) == [50.0, 50.0, 50.0]
    assert all(result["heat_score"] == 50 for result in analyze_grids([grid("A"), grid("B")]))


def test_ranking_and_tie_break_are_deterministic():
    a = grid("A", temperature=1, elderly_ratio=0, farmland_ratio=0, nearest_shelter_distance_m=0)
    b = grid("B", temperature=1, elderly_ratio=0, farmland_ratio=0, nearest_shelter_distance_m=0)
    high = grid("Z", temperature=2, elderly_ratio=1, farmland_ratio=1, nearest_shelter_distance_m=1)
    first = analyze_grids([b, high, a])
    ranks = {item["grid_id"]: item["installation_rank"] for item in first}
    assert ranks["Z"] == 1 and ranks["A"] < ranks["B"]
    assert first == analyze_grids([b, high, a])


def test_main_factors_descend_by_score_and_exclude_below_threshold():
    high = grid("HIGH", temperature=100, elderly_ratio=0.8, farmland_ratio=0.6, nearest_shelter_distance_m=1000)
    low = grid("LOW", temperature=0, elderly_ratio=0, farmland_ratio=0, nearest_shelter_distance_m=0)
    assert analyze_grids([high, low])[0]["main_factors"] == ["HIGH_HEAT", "HIGH_ELDERLY_RATIO", "HIGH_FARMLAND_RATIO"]


def test_mock_data_is_backend_shaped_and_analysis_is_deterministic():
    grids = json.loads((Path("mocks") / "grids.json").read_text(encoding="utf-8"))
    assert len(grids) == 25
    assert all("heat_exposure_value" not in item for item in grids)
    assert analyze_grids(grids) == analyze_grids(grids)
