from copy import deepcopy
import json
from pathlib import Path

import geopandas as gpd
import pytest
from pyproj import Transformer
from shapely.geometry import Point

from gis.placement_coverage import build_placement_coverage


def _to_wgs84(x, y):
    return Transformer.from_crs(5179, 4326, always_xy=True).transform(x, y)


def _grid_path(tmp_path):
    grids = gpd.GeoDataFrame(
        {"grid_id": ["G002", "G001", "G003"]},
        geometry=[Point(0, 0), Point(300, 0), Point(301, 0)],
        crs="EPSG:5179",
    ).to_crs(4326)
    path = tmp_path / "grid.geojson"
    grids.to_file(path, driver="GeoJSON")
    return path


def test_batch_coverage_uses_existing_300m_centroid_rule_and_preserves_input(tmp_path):
    lon, lat = _to_wgs84(0, 0)
    far_lon, far_lat = _to_wgs84(5000, 5000)
    placements = [
        {"placement_id": "near", "latitude": lat, "longitude": lon},
        {"placement_id": "far", "latitude": far_lat, "longitude": far_lon},
    ]
    original = deepcopy(placements)
    grid_path = _grid_path(tmp_path)
    result = build_placement_coverage(placements, grid_path)
    assert result == [
        {"placement_id": "near", "latitude": lat, "longitude": lon, "covered_grid_ids": ["G001", "G002"]},
        {"placement_id": "far", "latitude": far_lat, "longitude": far_lon, "covered_grid_ids": []},
    ]
    assert placements == original
    assert result == build_placement_coverage(placements, grid_path)


def test_single_placement_returns_sorted_grid_ids(tmp_path):
    lon, lat = _to_wgs84(0, 0)
    assert build_placement_coverage(
        [{"placement_id": "one", "latitude": lat, "longitude": lon}],
        _grid_path(tmp_path),
    ) == [{"placement_id": "one", "latitude": lat, "longitude": lon, "covered_grid_ids": ["G001", "G002"]}]


@pytest.mark.parametrize(
    "placements, message",
    [
        ([{"latitude": 35.5, "longitude": 128.1}], "placement_id"),
        ([{"placement_id": "same", "latitude": 35.5, "longitude": 128.1}, {"placement_id": "same", "latitude": 35.6, "longitude": 128.2}], "placement_id"),
        ([{"placement_id": "bad-lat", "latitude": 91, "longitude": 128.1}], "latitude"),
        ([{"placement_id": "bad-lon", "latitude": 35.5, "longitude": 181}], "longitude"),
        ([{"placement_id": "nan", "latitude": float("nan"), "longitude": 128.1}], "latitude"),
        ([{"placement_id": "inf", "latitude": 35.5, "longitude": float("inf")}], "longitude"),
    ],
)
def test_invalid_placements_are_rejected(placements, message):
    with pytest.raises(ValueError, match=message):
        build_placement_coverage(placements)


def test_existing_candidate_coordinates_match_runtime_wrapper():
    candidates = json.loads(
        (Path("data/processed/gis/hapcheon_candidate_coverage.json")).read_text(encoding="utf-8")
    )[:3]
    placements = [
        {"placement_id": candidate["candidate_id"], "latitude": candidate["latitude"], "longitude": candidate["longitude"]}
        for candidate in candidates
    ]
    actual = build_placement_coverage(placements)
    assert [item["covered_grid_ids"] for item in actual] == [candidate["covered_grid_ids"] for candidate in candidates]
