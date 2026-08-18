from copy import deepcopy
from pathlib import Path

import pandas as pd
import pytest
from pyproj import Transformer

from ai.analyzer import analyze_grids
from ai.normalization import fit_normalization_reference, normalize, transform_with_reference
from ai.scoring import placement_risk_level
from gis.build_shelter_accessibility import calculate_shelter_accessibility
from integration.placement_risk import simulate_placement_risk


ORIGIN_X = 1_000_000
ORIGIN_Y = 1_800_000


def _to_wgs84(x, y=ORIGIN_Y):
    return Transformer.from_crs(5179, 4326, always_xy=True).transform(x, y)


def _placement(placement_id, x):
    longitude, latitude = _to_wgs84(x)
    return {
        "placement_id": placement_id,
        "latitude": latitude,
        "longitude": longitude,
    }


def _scenario(component_score=80.0):
    grids = pd.DataFrame(
        {
            "grid_id": ["G-REF", "G-TARGET"],
            "centroid_x": [ORIGIN_X, ORIGIN_X + 1000],
            "centroid_y": [ORIGIN_Y, ORIGIN_Y],
            "elderly_population": [10, 20],
            "grid_area_m2": [250000, 250000],
        }
    )
    shelter_lon, shelter_lat = _to_wgs84(ORIGIN_X)
    shelters = pd.DataFrame(
        {
            "shelter_id": ["S-EXISTING"],
            "latitude": [shelter_lat],
            "longitude": [shelter_lon],
            "geocoding_status": ["OK"],
        }
    )
    accessibility = calculate_shelter_accessibility(grids, shelters)
    vulnerability_level = "VERY_HIGH" if component_score >= 75 else "HIGH"
    analysis = []
    for grid_id, gap_score in (("G-REF", 0.0), ("G-TARGET", 100.0)):
        installation = round(component_score * 0.75 + gap_score * 0.25, 2)
        analysis.append(
            {
                "grid_id": grid_id,
                "analysis_status": "OK",
                "heat_score": component_score,
                "elderly_score": component_score,
                "farmland_score": component_score,
                "coverage_gap_score": gap_score,
                "vulnerability_score": component_score,
                "risk_level": vulnerability_level,
                "installation_need_score": installation,
            }
        )
    return grids, analysis, accessibility, shelters


def _target(result):
    return next(item for item in result["grid_results"] if item["grid_id"] == "G-TARGET")


def test_zero_placements_keeps_before_and_after_identical():
    args = _scenario()
    result = simulate_placement_risk(*args, [])
    assert result["requested_shelter_count"] == 0
    assert result["newly_covered_grid_ids"] == []
    invariant_fields = (
        "nearest_shelter_distance_m",
        "shelter_count",
        "current_covered",
        "blind_spot",
        "vulnerability_score",
        "risk_level",
        "placement_risk_score",
        "placement_risk_level",
    )
    for item in result["grid_results"]:
        for field in invariant_fields:
            assert item["before"][field] == item["after"][field]
        assert item["newly_covered"] is False


def test_placement_risk_score_does_not_reuse_installation_need_score():
    grids, analysis, accessibility, shelters = _scenario()
    target_analysis = next(item for item in analysis if item["grid_id"] == "G-TARGET")
    target_analysis["installation_need_score"] = 1.23

    target = _target(
        simulate_placement_risk(grids, analysis, accessibility, shelters, [])
    )

    assert target["before"]["placement_risk_score"] == 85.0
    assert target["after"]["placement_risk_score"] == 85.0
    assert target_analysis["installation_need_score"] == 1.23


def test_real_3934_grid_zero_placement_regression():
    root = Path(__file__).resolve().parents[1]
    grids = pd.read_csv(
        root / "data/processed/integration/hapcheon_ai_grid_features.csv",
        dtype={"grid_id": "string"},
    )
    analysis = pd.read_csv(
        root / "data/processed/analysis/hapcheon_ai_analysis.csv",
        dtype={"grid_id": "string"},
    ).to_dict("records")
    accessibility = pd.read_csv(
        root / "data/processed/gis/hapcheon_grid_shelter_accessibility.csv",
        dtype={"grid_id": "string"},
    )

    result = simulate_placement_risk(
        grids,
        analysis,
        accessibility,
        pd.DataFrame(),
        [],
    )

    mismatches = [
        item["grid_id"]
        for item in result["grid_results"]
        if item["before"] != item["after"]
    ]
    assert len(result["grid_results"]) == 3934
    assert mismatches == []
    assert result["newly_covered_grid_ids"] == []
    assert all(item["newly_covered"] is False for item in result["grid_results"])


def test_new_shelter_changes_access_and_blind_spot_but_not_vulnerability():
    args = _scenario()
    result = simulate_placement_risk(*args, [_placement("P-TARGET", ORIGIN_X + 1000)])
    target = _target(result)
    assert target["before"]["current_covered"] is False
    assert target["after"]["current_covered"] is True
    assert target["before"]["blind_spot"] is True
    assert target["after"]["blind_spot"] is False
    assert target["newly_covered"] is True
    assert target["after"]["nearest_shelter_distance_m"] < target["before"]["nearest_shelter_distance_m"]
    assert target["after"]["placement_risk_score"] <= target["before"]["placement_risk_score"]
    assert target["before"]["vulnerability_score"] == target["after"]["vulnerability_score"]
    assert target["before"]["risk_level"] == target["after"]["risk_level"]


def test_access_improves_without_crossing_placement_risk_threshold():
    args = _scenario(component_score=73.3333333333)
    result = simulate_placement_risk(*args, [_placement("P-PARTIAL", ORIGIN_X + 160)])
    target = _target(result)
    assert target["before"]["placement_risk_score"] == pytest.approx(80.0, abs=0.01)
    assert target["after"]["placement_risk_score"] == pytest.approx(76.0, abs=0.01)
    assert target["before"]["placement_risk_level"] == "VERY_HIGH"
    assert target["after"]["placement_risk_level"] == "VERY_HIGH"
    assert target["newly_covered"] is False


def test_access_improvement_crosses_actual_threshold():
    args = _scenario(component_score=80.0)
    result = simulate_placement_risk(*args, [_placement("P-TARGET", ORIGIN_X + 1000)])
    target = _target(result)
    assert target["before"]["placement_risk_score"] == 85.0
    assert target["after"]["placement_risk_score"] == 60.0
    assert target["before"]["placement_risk_level"] == "VERY_HIGH"
    assert target["after"]["placement_risk_level"] == "HIGH"


def test_multiple_placements_are_counted_and_nearest_is_actual_minimum():
    args = _scenario()
    placements = [
        _placement("P-200", ORIGIN_X + 1200),
        _placement("P-100", ORIGIN_X + 1100),
    ]
    target = _target(simulate_placement_risk(*args, placements))
    assert target["after"]["shelter_count"] == 2
    assert target["after"]["nearest_shelter_distance_m"] == pytest.approx(100, abs=0.01)


def test_same_coordinates_with_distinct_placement_ids_are_counted_separately():
    args = _scenario()
    target = _target(
        simulate_placement_risk(
            *args,
            [
                _placement("P-SAME-1", ORIGIN_X + 1000),
                _placement("P-SAME-2", ORIGIN_X + 1000),
            ],
        )
    )
    assert target["after"]["nearest_shelter_distance_m"] == pytest.approx(0, abs=0.01)
    assert target["after"]["shelter_count"] == 2


@pytest.mark.parametrize(
    "field",
    ["nearest_shelter_distance_m", "shelter_count", "current_covered"],
)
def test_valid_analysis_fails_fast_when_baseline_accessibility_is_missing(field):
    grids, analysis, accessibility, shelters = _scenario()
    accessibility.loc[accessibility["grid_id"] == "G-TARGET", field] = None
    with pytest.raises(
        ValueError,
        match=rf"baseline accessibility field '{field}' is missing for grid_id: G-TARGET",
    ):
        simulate_placement_risk(grids, analysis, accessibility, shelters, [])


def test_exact_300m_boundary_is_covered():
    args = _scenario()
    target = _target(
        simulate_placement_risk(
            *args, [_placement("P-BOUNDARY", ORIGIN_X + 1300)]
        )
    )
    assert target["after"]["nearest_shelter_distance_m"] == pytest.approx(300, abs=0.01)
    assert target["after"]["current_covered"] is True
    assert target["after"]["shelter_count"] == 1
    assert target["newly_covered"] is True


@pytest.mark.parametrize(
    "score,expected",
    [
        (24.999, "LOW"),
        (25, "MODERATE"),
        (49.999, "MODERATE"),
        (50, "HIGH"),
        (74.999, "HIGH"),
        (75, "VERY_HIGH"),
    ],
)
def test_placement_risk_level_mvp_boundaries(score, expected):
    assert placement_risk_level(score) == expected


def test_fixed_normalization_reference_preserves_baseline_scale():
    values = [0, 500, 1000]
    reference = fit_normalization_reference(values)
    assert transform_with_reference(values, reference) == normalize(values)
    assert transform_with_reference([250], reference) == [25.0]


def test_inputs_are_not_mutated():
    grids, analysis, accessibility, shelters = _scenario()
    placements = [_placement("P-TARGET", ORIGIN_X + 1000)]
    original_grids = grids.copy(deep=True)
    original_analysis = deepcopy(analysis)
    original_accessibility = accessibility.copy(deep=True)
    original_shelters = shelters.copy(deep=True)
    original_placements = deepcopy(placements)
    simulate_placement_risk(grids, analysis, accessibility, shelters, placements)
    assert grids.equals(original_grids)
    assert analysis == original_analysis
    assert accessibility.equals(original_accessibility)
    assert shelters.equals(original_shelters)
    assert placements == original_placements


def test_incomplete_analysis_keeps_scores_null_instead_of_coercing_to_zero():
    grids, analysis, accessibility, shelters = _scenario()
    for result in analysis:
        result.update(
            analysis_status="INSUFFICIENT_DATA",
            coverage_gap_score=None,
            vulnerability_score=None,
            risk_level=None,
            installation_need_score=None,
        )
    result = simulate_placement_risk(
        grids,
        analysis,
        accessibility,
        shelters,
        [_placement("P-TARGET", ORIGIN_X + 1000)],
    )
    target = _target(result)
    assert target["before"]["placement_risk_score"] is None
    assert target["after"]["placement_risk_score"] is None
    assert target["before"]["placement_risk_level"] is None
    assert target["after"]["placement_risk_level"] is None


def test_existing_analyzer_formula_regression_snapshot():
    grids = [
        {
            "grid_id": "LOW",
            "temperature": 20,
            "humidity": 60,
            "elderly_ratio": 0,
            "farmland_ratio": 0,
            "nearest_shelter_distance_m": 0,
            "population": 10,
            "elderly_population": 0,
            "current_covered": True,
            "grid_area_m2": 250000,
        },
        {
            "grid_id": "HIGH",
            "temperature": 40,
            "humidity": 60,
            "elderly_ratio": 1,
            "farmland_ratio": 1,
            "nearest_shelter_distance_m": 1000,
            "population": 10,
            "elderly_population": 10,
            "current_covered": False,
            "grid_area_m2": 250000,
        },
    ]
    low, high = analyze_grids(grids)
    assert (low["vulnerability_score"], low["risk_level"], low["installation_need_score"]) == (
        0.0,
        "LOW",
        0.0,
    )
    assert (
        high["vulnerability_score"],
        high["risk_level"],
        high["installation_need_score"],
        high["blind_spot"],
    ) == (100.0, "VERY_HIGH", 100.0, True)
