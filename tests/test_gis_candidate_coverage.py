import json

import geopandas as gpd
import pandas as pd
import pytest
from pyproj import Transformer
from shapely.geometry import Point, box

from gis.build_candidate_coverage import build_candidate_coverage, write_candidate_coverage


def _to_wgs84(x, y):
    return Transformer.from_crs(5179, 4326, always_xy=True).transform(x, y)


def _boundaries():
    return gpd.GeoDataFrame(
        {"region_code": ["TEST"], "region_name": ["Test Region"]},
        geometry=[box(-10_000, -10_000, 10_000, 10_000)],
        crs="EPSG:5179",
    )


def test_candidate_coverage_includes_300m_sorts_ids_and_keeps_empty_candidate(tmp_path):
    centroids = [Point(0, 0), Point(300, 0), Point(301, 0)]
    grids = gpd.GeoDataFrame({"grid_id": ["G002", "G001", "G003"]}, geometry=centroids, crs="EPSG:5179").to_crs(4326)
    grid_path = tmp_path / "grid.geojson"
    grids.to_file(grid_path, driver="GeoJSON")
    lon, lat = _to_wgs84(0, 0)
    far_lon, far_lat = _to_wgs84(5000, 5000)
    candidates = pd.DataFrame({"candidate_id": ["C001", "C002"], "candidate_name": ["Near", "Far"], "candidate_type": ["A", "A"], "latitude": [lat, far_lat], "longitude": [lon, far_lon]})
    candidate_path = tmp_path / "candidates.csv"
    candidates.to_csv(candidate_path, index=False)
    original_grid_bytes = grid_path.read_bytes()
    original_candidate_bytes = candidate_path.read_bytes()

    result, report = build_candidate_coverage(grid_path, candidate_path, _boundaries())
    repeated, repeated_report = build_candidate_coverage(grid_path, candidate_path, _boundaries())
    assert result.set_index("candidate_id").loc["C001", "covered_grid_ids"] == ["G001", "G002"]
    assert result.set_index("candidate_id").loc["C002", "covered_grid_ids"] == []
    assert report["covered_candidate_count"] == 1 and report["empty_coverage_candidate_count"] == 1
    assert result.equals(repeated) and report == repeated_report
    assert grid_path.read_bytes() == original_grid_bytes
    assert candidate_path.read_bytes() == original_candidate_bytes


def test_duplicate_candidate_id_is_invalid(tmp_path):
    grid = gpd.GeoDataFrame({"grid_id": ["G001"]}, geometry=[Point(0, 0)], crs="EPSG:5179").to_crs(4326)
    grid_path = tmp_path / "grid.geojson"
    grid.to_file(grid_path, driver="GeoJSON")
    lon, lat = _to_wgs84(0, 0)
    candidates = pd.DataFrame({"candidate_id": ["C001", "C001"], "candidate_name": ["A", "B"], "candidate_type": ["A", "A"], "latitude": [lat, lat], "longitude": [lon, lon]})
    candidate_path = tmp_path / "candidates.csv"
    candidates.to_csv(candidate_path, index=False)
    with pytest.raises(ValueError, match="candidate_id"):
        build_candidate_coverage(grid_path, candidate_path, _boundaries())


def test_candidate_output_serializes_json_arrays(tmp_path):
    coverage = pd.DataFrame({"candidate_id": ["C001"], "candidate_name": ["A"], "candidate_type": ["A"], "region_code": [None], "region_name": [None], "latitude": [35.0], "longitude": [127.0], "covered_grid_ids": [["G001", "G002"]]})
    write_candidate_coverage(coverage, tmp_path)
    assert json.loads(pd.read_csv(tmp_path / "hapcheon_candidate_coverage.csv").loc[0, "covered_grid_ids"]) == ["G001", "G002"]
    assert json.loads((tmp_path / "hapcheon_candidate_coverage.json").read_text(encoding="utf-8"))[0]["covered_grid_ids"] == ["G001", "G002"]
