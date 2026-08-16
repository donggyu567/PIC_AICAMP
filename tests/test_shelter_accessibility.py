import io

import geopandas as gpd
import pandas as pd
import pytest
from pyproj import Transformer
from shapely.geometry import Point

from gis.build_shelter_accessibility import build_shelter_accessibility
from gis.config import GRID_CSV
from gis.geocode_shelters import GeocodingResult, KakaoAddressGeocoder, geocode_shelters, prepare_geocoding_input


def _to_wgs84(x, y):
    return Transformer.from_crs(5179, 4326, always_xy=True).transform(x, y)


def _prepared_source():
    return pd.DataFrame({
        "shelter_id": ["SHELTER_001", "SHELTER_002"],
        "facility_name": ["A", "B"], "road_address": ["Road A", "Road B"], "lot_address": ["Lot A", "Lot B"],
        "geocoding_query": ["Road A", "Road B"], "fallback_query": ["Lot A", "Lot B"],
    })


def test_kakao_geocoding_parses_one_valid_address(monkeypatch):
    class Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr("gis.geocode_shelters.urlopen", lambda *args, **kwargs: Response(b'{"documents":[{"x":"127.9","y":"35.5"}]}'))
    result = KakaoAddressGeocoder("test-key").geocode("some address")
    assert result == GeocodingResult(status="OK", latitude=35.5, longitude=127.9, source="kakao")


def test_geocoding_failure_keeps_null_coordinates_and_input_is_not_mutated():
    class FailingGeocoder:
        def geocode(self, query):
            return GeocodingResult(status="FAILED", source="stub")

    source = _prepared_source()
    original = source.copy(deep=True)
    result, report = geocode_shelters(source, FailingGeocoder())
    assert source.equals(original)
    assert result["geocoding_status"].tolist() == ["FAILED", "FAILED"]
    assert result["latitude"].isna().all() and result["longitude"].isna().all()
    assert report["valid_geocoded_count"] == 0 and report["failed_count"] == 2


def test_prepare_geocoding_input_is_deterministic_and_rejects_duplicate_addresses(tmp_path):
    source = pd.DataFrame({"facility_name": ["B", "A"], "road_address": ["Road B", "Road A"], "lot_address": ["Lot B", "Lot A"]})
    path = tmp_path / "shelters.csv"
    source.to_csv(path, index=False)
    first, report = prepare_geocoding_input(path)
    second, _ = prepare_geocoding_input(path)
    assert first["shelter_id"].tolist() == ["SHELTER_001", "SHELTER_002"]
    assert first["facility_name"].tolist() == ["A", "B"]
    assert first.equals(second) and report["raw_shelter_count"] == 2
    source.assign(road_address=["same", "same"]).to_csv(path, index=False)
    with pytest.raises(ValueError, match="duplicate addresses"):
        prepare_geocoding_input(path)


def _write_accessibility_inputs(tmp_path, statuses=("OK",)):
    origin_x, origin_y = 1_000_000, 1_800_000
    grids = pd.DataFrame({"grid_id": ["G000", "G300", "G301"], "centroid_x": [origin_x, origin_x + 300, origin_x + 301], "centroid_y": [origin_y] * 3})
    grid_path = tmp_path / "grid.csv"
    grids.to_csv(grid_path, index=False)
    lon, lat = _to_wgs84(origin_x, origin_y)
    shelters = pd.DataFrame({"shelter_id": [f"S{index}" for index in range(len(statuses))], "latitude": [lat] * len(statuses), "longitude": [lon] * len(statuses), "geocoding_status": list(statuses)})
    shelter_path = tmp_path / "shelters.csv"
    shelters.to_csv(shelter_path, index=False)
    return grid_path, shelter_path


def test_accessibility_uses_epsg5179_and_includes_exactly_300m(tmp_path):
    grid_path, shelter_path = _write_accessibility_inputs(tmp_path)
    result, report = build_shelter_accessibility(grid_path, shelter_path)
    indexed = result.set_index("grid_id")
    assert indexed.loc["G000", "nearest_shelter_distance_m"] == pytest.approx(0, abs=0.01)
    assert indexed.loc["G300", "nearest_shelter_distance_m"] == pytest.approx(300, abs=0.01)
    assert bool(indexed.loc["G300", "current_covered"]) is True
    assert bool(indexed.loc["G301", "current_covered"]) is False
    assert indexed.loc["G000", "shelter_count"] == 1
    assert indexed.loc["G301", "shelter_count"] == 0
    assert report["current_covered_true_count"] == 2 and report["current_covered_false_count"] == 1


def test_accessibility_distinguishes_zero_coverage_from_no_valid_shelters_and_is_deterministic(tmp_path):
    grid_path, shelter_path = _write_accessibility_inputs(tmp_path, statuses=("FAILED",))
    no_valid, report = build_shelter_accessibility(grid_path, shelter_path)
    assert no_valid["nearest_shelter_distance_m"].isna().all()
    assert no_valid["current_covered"].isna().all() and no_valid["shelter_count"].isna().all()
    assert report["current_covered_null_count"] == 3
    grid_path, shelter_path = _write_accessibility_inputs(tmp_path, statuses=("OK",))
    first, _ = build_shelter_accessibility(grid_path, shelter_path)
    second, _ = build_shelter_accessibility(grid_path, shelter_path)
    assert first.equals(second) and first["grid_id"].is_unique


def test_real_grid_is_preserved_at_3934_rows_when_no_valid_shelters(tmp_path):
    shelters = pd.DataFrame({"shelter_id": ["S001"], "latitude": [None], "longitude": [None], "geocoding_status": ["FAILED"]})
    shelter_path = tmp_path / "failed_shelters.csv"
    shelters.to_csv(shelter_path, index=False)
    result, _ = build_shelter_accessibility(GRID_CSV, shelter_path)
    assert len(result) == 3934
    assert result["grid_id"].notna().all() and result["grid_id"].is_unique
