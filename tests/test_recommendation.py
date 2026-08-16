from copy import deepcopy

import pytest

from ai.recommendation import recommend_shelters


def grid(grid_id, elderly_population=10, installation_need_score=50, blind_spot=True, **changes):
    value = {
        "grid_id": grid_id,
        "elderly_population": elderly_population,
        "installation_need_score": installation_need_score,
        "blind_spot": blind_spot,
        "current_covered": False,
    }
    value.update(changes)
    return value


def candidate(candidate_id, covered_grid_ids):
    return {"candidate_id": candidate_id, "covered_grid_ids": covered_grid_ids}


def test_elderly_gain_and_marginal_gain_are_recalculated_without_overlap():
    grids = [grid("G001", 100), grid("G002", 50), grid("G003", 80)]
    candidates = [candidate("C001", ["G001", "G002"]), candidate("C002", ["G002", "G003"])]
    result = recommend_shelters(grids, candidates, 2)
    assert [item["candidate_id"] for item in result] == ["C001", "C002"]
    assert result[0]["newly_covered_grid_ids"] == ["G001", "G002"]
    assert result[0]["newly_covered_elderly_population"] == 150
    assert result[1]["newly_covered_grid_ids"] == ["G003"]
    assert result[1]["newly_covered_elderly_population"] == 80


def test_equal_elderly_gain_uses_installation_need_score_then_candidate_id():
    grids = [grid("G001", 100, 40), grid("G002", 100, 80)]
    result = recommend_shelters(grids, [candidate("C002", ["G001"]), candidate("C001", ["G002"])], 1)
    assert result[0]["candidate_id"] == "C001"

    tied_grids = [grid("G001", 100, 80), grid("G002", 100, 80)]
    tied = recommend_shelters(tied_grids, [candidate("C002", ["G001"]), candidate("C001", ["G002"])], 1)
    assert tied[0]["candidate_id"] == "C001"


def test_non_target_blind_spots_are_excluded_not_invalid():
    grids = [grid("G001", 10, 60, True), grid("G002", 999, 100, False), grid("G003", 999, 100, None)]
    result = recommend_shelters(grids, [candidate("C001", ["G003", "G002", "G001"])], 1)
    assert result[0]["newly_covered_grid_ids"] == ["G001"]
    assert result[0]["newly_covered_elderly_population"] == 10


def test_candidate_internal_duplicate_coverage_is_counted_once():
    result = recommend_shelters([grid("G001", 10), grid("G002", 20)], [candidate("C001", ["G002", "G001", "G001"])], 1)
    assert result[0]["newly_covered_grid_ids"] == ["G001", "G002"]
    assert result[0]["newly_covered_elderly_population"] == 30


def test_maximum_count_zero_gain_and_zero_shelter_stopping_cases():
    grids = [grid("G001", 10)]
    candidates = [candidate("C001", ["G001"]), candidate("C002", [])]
    assert len(recommend_shelters(grids, candidates, 5)) == 1
    assert recommend_shelters(grids, [candidate("C001", [])], 1) == []
    assert recommend_shelters(grids, candidates, 0) == []


def test_zero_elderly_population_is_valid_and_uses_need_score_tie_break():
    grids = [grid("G001", 0, 30), grid("G002", 0, 70)]
    result = recommend_shelters(grids, [candidate("C001", ["G001"]), candidate("C002", ["G002"])], 1)
    assert result[0]["candidate_id"] == "C002"
    assert result[0]["newly_covered_elderly_population"] == 0


@pytest.mark.parametrize("changes", [
    {"elderly_population": None}, {"installation_need_score": None}, {"elderly_population": -1},
    {"installation_need_score": -0.1}, {"installation_need_score": 100.1},
])
def test_invalid_target_grid_values_raise_value_error(changes):
    with pytest.raises(ValueError):
        recommend_shelters([grid("G001", **changes)], [candidate("C001", ["G001"])], 1)


def test_duplicate_ids_unknown_coverage_and_non_list_coverage_are_invalid():
    with pytest.raises(ValueError, match="duplicate grid_id"):
        recommend_shelters([grid("G001"), grid("G001")], [], 1)
    with pytest.raises(ValueError, match="duplicate candidate_id"):
        recommend_shelters([grid("G001")], [candidate("C001", []), candidate("C001", [])], 1)
    with pytest.raises(ValueError, match="unknown grid_id"):
        recommend_shelters([grid("G001")], [candidate("C001", ["G999"])], 1)
    with pytest.raises(ValueError, match="covered_grid_ids"):
        recommend_shelters([grid("G001")], [{"candidate_id": "C001", "covered_grid_ids": "G001"}], 1)


@pytest.mark.parametrize("n_shelters", [-1, 1.5, True, "1"])
def test_invalid_shelter_count_raises_value_error(n_shelters):
    with pytest.raises(ValueError):
        recommend_shelters([], [], n_shelters)


def test_recommendation_is_deterministic_and_does_not_mutate_input():
    grids = [grid("G001", 20), grid("G002", 10)]
    candidates = [candidate("C002", ["G001", "G002"]), candidate("C001", ["G001"])]
    original_grids, original_candidates = deepcopy(grids), deepcopy(candidates)
    first = recommend_shelters(grids, candidates, 2)
    assert first == recommend_shelters(grids, candidates, 2)
    assert grids == original_grids
    assert candidates == original_candidates
    assert all(item["recommendation_reasons"] == [] for item in first)
