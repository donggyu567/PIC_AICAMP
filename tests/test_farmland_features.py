import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Polygon, box

from gis.build_farmland_features import calculate_farmland_features


def _grids():
    return gpd.GeoDataFrame(
        {"grid_id": ["G1", "G2", "G3"], "analysis_area_m2": [100.0, 50.0, 100.0]},
        geometry=[box(0, 0, 10, 10), box(10, 0, 15, 10), box(20, 0, 30, 10)], crs="EPSG:5179",
    )


def _farmmap():
    return gpd.GeoDataFrame(
        {"CLSF_CD": ["01", "02", "03", "04", "06", "99", "01"]},
        geometry=[
            box(0, 0, 5, 10), box(4, 0, 6, 10), box(6, 0, 7, 10), box(7, 0, 8, 10),
            box(8, 0, 10, 10), box(9, 0, 10, 10), box(14, 0, 16, 10),
        ], crs="EPSG:5179",
    )


def test_farmland_codes_overlap_and_boundary_intersection():
    result, report = calculate_farmland_features(_grids(), _farmmap())
    values = result.set_index("grid_id")
    # 01/02/03/04 union occupies 0..8; 06 and unknown are excluded.
    assert values.loc["G1", "farmland_area_m2"] == pytest.approx(80)
    assert values.loc["G1", "farmland_ratio"] == pytest.approx(0.8)
    # The source 01 polygon extends outside the boundary-clipped G2 geometry.
    assert values.loc["G2", "farmland_area_m2"] == pytest.approx(10)
    assert values.loc["G2", "farmland_ratio"] == pytest.approx(0.2)
    assert values.loc["G3", "farmland_area_m2"] == 0
    assert values.loc["G3", "farmland_ratio"] == 0
    assert report["unknown_code_counts"] == {"99": 1}
    assert report["intersection_overlap_detected"] is True
    assert report["overlap_area_removed_m2"] == pytest.approx(10)


def test_farmland_ratio_uses_analysis_area_and_preserves_grid_ids_deterministically():
    grids = _grids()
    farmmap = _farmmap()
    original_grid_wkb = grids.geometry.to_wkb().copy()
    original_farm_wkb = farmmap.geometry.to_wkb().copy()
    first, _ = calculate_farmland_features(grids, farmmap)
    second, _ = calculate_farmland_features(grids, farmmap)
    assert first.equals(second)
    assert first["grid_id"].tolist() == ["G1", "G2", "G3"]
    assert first["grid_id"].is_unique and first["grid_id"].notna().all()
    assert first["farmland_ratio"].between(0, 1).all()
    assert grids.geometry.to_wkb().equals(original_grid_wkb)
    assert farmmap.geometry.to_wkb().equals(original_farm_wkb)


def test_invalid_and_empty_geometry_are_reported_without_mutating_inputs():
    invalid = Polygon([(0, 0), (10, 10), (10, 0), (0, 10), (0, 0)])
    farmmap = gpd.GeoDataFrame({"CLSF_CD": ["01", "06"]}, geometry=[invalid, Polygon()], crs="EPSG:5179")
    original_wkb = farmmap.geometry.to_wkb().copy()
    result, report = calculate_farmland_features(_grids(), farmmap)
    assert report["invalid_geometry_before"] == 1
    assert report["invalid_geometry_after"] == 0
    assert report["empty_geometry_count"] == 1
    assert (result["farmland_area_m2"] >= 0).all()
    assert farmmap.geometry.to_wkb().equals(original_wkb)


def test_invalid_analysis_area_is_rejected():
    grids = _grids()
    grids.loc[0, "analysis_area_m2"] = 0
    with pytest.raises(ValueError, match="analysis_area_m2"):
        calculate_farmland_features(grids, _farmmap())
