from copy import deepcopy

import pytest

from ai.coverage import calculate_coverage_comparison


def grid(grid_id, elderly_population=100, *, status="OK", risk="HIGH", covered=False, blind=True, area=250000):
    return {
        "grid_id": grid_id,
        "analysis_status": status,
        "risk_level": risk,
        "elderly_population": elderly_population,
        "current_covered": covered,
        "blind_spot": blind,
        "grid_area_m2": area,
    }


def recommendation(*grid_ids):
    return {"candidate_id": "C001", "recommendation_rank": 1, "newly_covered_grid_ids": list(grid_ids)}


def test_before_after_population_rates_counts_and_area():
    grids = [
        grid("G001", 200, covered=True, blind=False, area=100),
        grid("G002", 150, covered=False, blind=True, area=200),
        grid("G003", 150, covered=False, blind=True, area=300),
    ]
    result = calculate_coverage_comparison(grids, [recommendation("G002")])
    assert result == {
        "total_vulnerable_population": 500,
        "before": {"covered_vulnerable_population": 200, "vulnerable_population_coverage_rate": 0.4, "blind_spot_grid_count": 2, "blind_spot_area_m2": 500},
        "after": {"covered_vulnerable_population": 350, "vulnerable_population_coverage_rate": 0.7, "blind_spot_grid_count": 1, "blind_spot_area_m2": 300},
        "improvement": {"newly_covered_vulnerable_population": 150, "vulnerable_population_coverage_rate_delta": pytest.approx(0.3), "blind_spot_grid_reduction_count": 1},
    }


def test_duplicate_recommendation_coverage_is_counted_once_and_all_blind_spots_can_be_removed():
    grids = [grid("G001", 100), grid("G002", 50)]
    recommendations = [recommendation("G001", "G002"), {"candidate_id": "C002", "recommendation_rank": 2, "newly_covered_grid_ids": ["G002"]}]
    result = calculate_coverage_comparison(grids, recommendations)
    assert result["after"]["covered_vulnerable_population"] == 150
    assert result["after"]["blind_spot_grid_count"] == 0
    assert result["improvement"]["blind_spot_grid_reduction_count"] == 2


def test_empty_recommendations_leave_before_and_after_equal():
    result = calculate_coverage_comparison([grid("G001", 100, covered=True, blind=False), grid("G002", 50)], [])
    assert result["before"] == result["after"]
    assert result["improvement"] == {
        "newly_covered_vulnerable_population": 0,
        "vulnerable_population_coverage_rate_delta": 0.0,
        "blind_spot_grid_reduction_count": 0,
    }


def test_only_ok_high_or_very_high_grids_with_known_coverage_are_vulnerable():
    grids = [
        grid("G001", 100, covered=True, blind=False),
        grid("G002", 500, risk="LOW", covered=True, blind=False),
        grid("G003", 500, risk="MODERATE", covered=True, blind=False),
        grid("G004", 500, status="INVALID_DATA", covered=True, blind=False),
        grid("G005", 500, risk="VERY_HIGH", covered=None, blind=None),
    ]
    result = calculate_coverage_comparison(grids, [])
    assert result["total_vulnerable_population"] == 100
    assert result["before"]["covered_vulnerable_population"] == 100


def test_zero_vulnerable_population_returns_null_rates_and_zero_is_valid():
    result = calculate_coverage_comparison([grid("G001", 0, covered=True, blind=False)], [])
    assert result["total_vulnerable_population"] == 0
    assert result["before"]["vulnerable_population_coverage_rate"] is None
    assert result["after"]["vulnerable_population_coverage_rate"] is None
    assert result["improvement"]["vulnerable_population_coverage_rate_delta"] is None


@pytest.mark.parametrize("changes", [
    {"elderly_population": None}, {"elderly_population": -1}, {"elderly_population": True},
])
def test_invalid_vulnerable_elderly_population_is_not_treated_as_zero(changes):
    item = grid("G001") | changes
    with pytest.raises(ValueError, match="elderly_population"):
        calculate_coverage_comparison([item], [])


def test_duplicate_grid_id_and_invalid_coverage_state_are_rejected():
    with pytest.raises(ValueError, match="duplicate grid_id"):
        calculate_coverage_comparison([grid("G001"), grid("G001")], [])
    with pytest.raises(ValueError, match="current_covered"):
        calculate_coverage_comparison([grid("G001", covered="false")], [])


@pytest.mark.parametrize("covered_ids,match", [
    (["G999"], "unknown grid_id"), (["G001"], "not a vulnerable blind_spot"),
])
def test_recommendations_must_reference_existing_vulnerable_blind_spots(covered_ids, match):
    grids = [grid("G001", blind=False)]
    with pytest.raises(ValueError, match=match):
        calculate_coverage_comparison(grids, [recommendation(*covered_ids)])


def test_recommendation_cannot_reference_null_blind_spot():
    with pytest.raises(ValueError, match="not a vulnerable blind_spot"):
        calculate_coverage_comparison([grid("G001", blind=None)], [recommendation("G001")])


def test_missing_area_makes_both_blind_spot_area_metrics_null():
    result = calculate_coverage_comparison([grid("G001", area=100), grid("G002", area=None)], [recommendation("G001")])
    assert result["before"]["blind_spot_area_m2"] is None
    assert result["after"]["blind_spot_area_m2"] is None


def test_input_is_not_mutated_and_output_is_deterministic():
    grids = [grid("G001", 100), grid("G002", 50)]
    recommendations = [recommendation("G001")]
    original_grids, original_recommendations = deepcopy(grids), deepcopy(recommendations)
    first = calculate_coverage_comparison(grids, recommendations)
    assert first == calculate_coverage_comparison(grids, recommendations)
    assert grids == original_grids
    assert recommendations == original_recommendations
