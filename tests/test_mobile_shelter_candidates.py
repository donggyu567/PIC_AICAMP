import json

import geopandas as gpd
import pandas as pd
import pytest
from pyproj import Transformer
from shapely.geometry import Point

from gis.build_mobile_shelter_candidates import (
    CANDIDATE_TYPE,
    build_mobile_shelter_candidates,
    write_mobile_shelter_candidates,
)


def _grid_file(tmp_path):
    grids = gpd.GeoDataFrame(
        {"grid_id": ["G003", "G001", "G002"]},
        geometry=[Point(1000, 0), Point(0, 0), Point(300, 0)],
        crs="EPSG:5179",
    ).to_crs(4326)
    path = tmp_path / "grid.geojson"
    grids.to_file(path, driver="GeoJSON")
    return path


def _sources():
    to_wgs84 = Transformer.from_crs(5179, 4326, always_xy=True)
    coordinates = [to_wgs84.transform(x, 0) for x in (0, 300, 1000)]
    features = pd.DataFrame(
        {
            "grid_id": ["G001", "G002", "G003"],
            "region_code": ["R1", "R1", "R2"],
            "region_name": ["One", "One", "Two"],
            "current_covered": [False, True, False],
            "longitude": [coordinate[0] for coordinate in coordinates],
            "latitude": [coordinate[1] for coordinate in coordinates],
        }
    )
    analysis = pd.DataFrame(
        {
            "grid_id": ["G001", "G002", "G003"],
            "blind_spot": [True, True, False],
        }
    )
    return features, analysis


def test_builds_only_uncovered_blind_spot_centroids_with_existing_coverage_helper(tmp_path):
    features, analysis = _sources()
    result, report = build_mobile_shelter_candidates(features, analysis, _grid_file(tmp_path))

    assert result.to_dict("records") == [
        {
            "candidate_id": "MOBILE_G001",
            "candidate_name": "경상남도 합천군 One 일대",
            "candidate_type": CANDIDATE_TYPE,
            "region_code": "R1",
            "region_name": "One",
            "latitude": pytest.approx(features.loc[0, "latitude"]),
            "longitude": pytest.approx(features.loc[0, "longitude"]),
            "covered_grid_ids": ["G001", "G002"],
        }
    ]
    assert report == {
        "candidate_count": 1,
        "candidate_id_duplicate_count": 0,
        "coordinate_null_count": 0,
        "empty_coverage_candidate_count": 0,
        "source_uncovered_count": 1,
        "source_blind_spot_count": 1,
    }


def test_output_is_deterministic_and_preserves_legacy_contract(tmp_path):
    features, analysis = _sources()
    first, first_report = build_mobile_shelter_candidates(features, analysis, _grid_file(tmp_path))
    repeated, repeated_report = build_mobile_shelter_candidates(
        features.sample(frac=1, random_state=1),
        analysis.sample(frac=1, random_state=2),
        tmp_path / "grid.geojson",
    )
    assert first.equals(repeated)
    assert first_report == repeated_report
    assert list(first.columns) == [
        "candidate_id", "candidate_name", "candidate_type", "region_code",
        "region_name", "latitude", "longitude", "covered_grid_ids",
    ]

    output_path = tmp_path / "mobile.json"
    write_mobile_shelter_candidates(first, output_path)
    assert json.loads(output_path.read_text(encoding="utf-8"))[0]["candidate_id"] == "MOBILE_G001"


def test_source_grid_ids_must_match(tmp_path):
    features, analysis = _sources()
    with pytest.raises(ValueError, match="grid_ids must match"):
        build_mobile_shelter_candidates(
            features.iloc[:-1], analysis, _grid_file(tmp_path)
        )
