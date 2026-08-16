import pandas as pd
import pytest

from integration.build_ai_input import assemble_ai_grid_features


def _inputs():
    base = pd.DataFrame({
        "grid_id": ["G2", "G1", "G3"], "region_code": ["R", "R", "R"], "region_name": ["Region"] * 3,
        "grid_area_m2": [250000] * 3, "analysis_area_m2": [250000] * 3, "centroid_x": [1, 2, 3], "centroid_y": [1, 2, 3],
        "longitude": [127.0] * 3, "latitude": [35.0] * 3, "population": [999, 999, 999],
    })
    shelter = pd.DataFrame({"grid_id": ["G1", "G2", "G3"], "nearest_shelter_distance_m": [100, 400, 0], "current_covered": [True, False, True]})
    farmland = pd.DataFrame({"grid_id": ["G1", "G2", "G3"], "farmland_area_m2": [0, 50, 0], "farmland_ratio": [0.0, 0.2, 0.0]})
    elderly = pd.DataFrame({"grid_id": ["G1", "G2", "G3"], "population": [100, 200, None], "elderly_population": [10, 20, None], "elderly_ratio": [0.1, 0.1, None]})
    return base, shelter, farmland, elderly


def test_left_join_preserves_base_grid_ngii_population_and_missing_values():
    base, shelter, farmland, elderly = _inputs()
    originals = [item.copy(deep=True) for item in (base, shelter, farmland, elderly)]
    result, report = assemble_ai_grid_features(base, shelter, farmland, elderly)
    assert result["grid_id"].tolist() == ["G1", "G2", "G3"]
    assert len(result) == 3 and result["grid_id"].is_unique
    assert result.set_index("grid_id").loc["G1", "population"] == 100  # NGII, never legacy SGIS 999.
    assert pd.isna(result.set_index("grid_id").loc["G3", "elderly_ratio"])
    assert result.set_index("grid_id").loc["G1", "farmland_ratio"] == 0
    assert bool(result.set_index("grid_id").loc["G2", "current_covered"]) is False
    assert report["spatial_feature_complete_count"] == 2
    for current, original in zip((base, shelter, farmland, elderly), originals):
        assert current.equals(original)


def test_duplicate_or_missing_feature_grid_ids_are_rejected():
    base, shelter, farmland, elderly = _inputs()
    with pytest.raises(ValueError, match="invalid"):
        assemble_ai_grid_features(base, pd.concat([shelter, shelter.iloc[[0]]]), farmland, elderly)
    with pytest.raises(ValueError, match="invalid"):
        assemble_ai_grid_features(base, shelter, farmland.drop(columns="farmland_ratio"), elderly)


def test_left_join_does_not_drop_unmatched_base_grid_and_is_deterministic():
    base, shelter, farmland, elderly = _inputs()
    shelter = shelter[shelter.grid_id != "G3"]
    first, report = assemble_ai_grid_features(base, shelter, farmland, elderly)
    second, _ = assemble_ai_grid_features(base, shelter, farmland, elderly)
    assert len(first) == 3 and pd.isna(first.set_index("grid_id").loc["G3", "nearest_shelter_distance_m"])
    assert report["shelter_unmatched_count"] == 1
    assert first.equals(second)
