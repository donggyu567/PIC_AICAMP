import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import box

from gis.build_elderly_features import calculate_elderly_features, map_sgis_to_ngii


def _mapping():
    return pd.DataFrame({"grid_id": ["G1", "G2", "G3", "G4"], "gid": ["N1", "N2", "N3", "N4"]})


def _ngii(values):
    return gpd.GeoDataFrame({"gid": ["N1", "N2", "N3", "N4"], "val": values}, geometry=[box(i * 10, 0, i * 10 + 10, 10) for i in range(4)], crs="EPSG:5179")


def test_ngii_ratio_uses_matched_ngii_population_and_preserves_zero_and_null():
    population = _ngii([100, 0, None, 100])
    elderly = _ngii([25, 0, None, None])
    original_population = population.copy(deep=True)
    original_elderly = elderly.copy(deep=True)
    result, report = calculate_elderly_features(_mapping(), population, elderly)
    values = result.set_index("grid_id")
    assert values.loc["G1", "population"] == 100 and values.loc["G1", "elderly_ratio"] == 0.25
    assert pd.isna(values.loc["G2", "elderly_ratio"])  # 0/0 is not interpreted as 0%.
    assert pd.isna(values.loc["G3", "population"]) and pd.isna(values.loc["G3", "elderly_population"]) and pd.isna(values.loc["G3", "elderly_ratio"])
    assert values.loc["G4", "population"] == 100 and pd.isna(values.loc["G4", "elderly_population"]) and pd.isna(values.loc["G4", "elderly_ratio"])
    assert population.equals(original_population) and elderly.equals(original_elderly)
    assert report["elderly_over_population_count"] == 0


def test_actual_elderly_zero_with_population_positive_is_zero_ratio_and_output_is_deterministic():
    population = _ngii([100, 100, 100, 100])
    elderly = _ngii([0, 50, 100, 1])
    first, _ = calculate_elderly_features(_mapping(), population, elderly)
    second, _ = calculate_elderly_features(_mapping(), population, elderly)
    assert first.equals(second)
    assert first["grid_id"].tolist() == ["G1", "G2", "G3", "G4"]
    assert first.set_index("grid_id").loc["G1", "elderly_ratio"] == 0
    assert first["elderly_ratio"].between(0, 1).all()
    # The 100 denominator is NGII population in this fixture, not an SGIS value.
    assert first.set_index("grid_id").loc["G2", "elderly_ratio"] == 0.5


@pytest.mark.parametrize("population_values,elderly_values", [([0, 1, 1, 1], [1, 0, 0, 0]), ([1, 1, 1, 1], [2, 0, 0, 0]), ([-1, 1, 1, 1], [0, 0, 0, 0]), ([1, 1, 1, 1], [-1, 0, 0, 0])])
def test_invalid_population_elderly_combinations_are_rejected(population_values, elderly_values):
    with pytest.raises(ValueError, match="invalid"):
        calculate_elderly_features(_mapping(), _ngii(population_values), _ngii(elderly_values))


def test_geometry_mapping_requires_deterministic_one_to_one_exact_match():
    sgis = gpd.GeoDataFrame({"grid_id": ["G1", "G2"]}, geometry=[box(0, 0, 10, 10), box(10, 0, 20, 10)], crs="EPSG:5179")
    ngii = gpd.GeoDataFrame({"gid": ["N2", "N1"], "val": [1, 2]}, geometry=[box(10, 0, 20, 10), box(0, 0, 10, 10)], crs="EPSG:5179")
    mapping = map_sgis_to_ngii(sgis, ngii)
    assert mapping.to_dict("records") == [{"grid_id": "G1", "gid": "N1"}, {"grid_id": "G2", "gid": "N2"}]
    duplicate = pd.concat([ngii, ngii.iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="unique"):
        map_sgis_to_ngii(sgis, duplicate)
    shifted = ngii.copy(); shifted.geometry = shifted.translate(xoff=1)
    with pytest.raises(ValueError, match="centroids"):
        map_sgis_to_ngii(sgis, shifted)
