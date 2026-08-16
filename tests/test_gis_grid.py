from pathlib import Path
import zipfile

import geopandas as gpd
import pandas as pd
from shapely.geometry import box

from gis.build_hapcheon_grid import build_hapcheon_grid, write_hapcheon_grid


def _write_zipped_shapefile(data: gpd.GeoDataFrame, path: Path, stem: str) -> Path:
    source = path.parent / stem
    source.mkdir()
    shapefile = source / f"{stem}.shp"
    data.to_file(shapefile)
    archive = path / f"{stem}.zip"
    with zipfile.ZipFile(archive, "w") as zipped:
        for file in source.iterdir():
            zipped.write(file, arcname=f"{stem}/{file.name}")
    return archive


def test_centroid_selection_region_mapping_population_null_and_areas(tmp_path):
    boundaries = gpd.GeoDataFrame(
        {"A1": [f"R{index}" for index in range(17)], "A2": [f"Region {index}" for index in range(17)]},
        geometry=[box(index * 500, 0, (index + 1) * 500, 500) for index in range(17)], crs="EPSG:5179",
    )
    grids = gpd.GeoDataFrame(
        {"GRID_CD": ["IN1", "IN2", "OUT"]},
        geometry=[box(0, 0, 500, 500), box(500, 0, 1000, 500), box(9000, 0, 9500, 500)], crs="EPSG:5179",
    )
    boundary_zip = _write_zipped_shapefile(boundaries, tmp_path, "boundary")
    grid_zip = _write_zipped_shapefile(grids, tmp_path, "grid")
    population_csv = tmp_path / "population.csv"
    pd.DataFrame({"grid_id": ["IN1"], "population": [0]}).to_csv(population_csv, index=False)

    result, report = build_hapcheon_grid(boundary_zip, grid_zip, population_csv)
    assert result["grid_id"].tolist() == ["IN1", "IN2"]
    assert result.set_index("grid_id").loc["IN1", "region_code"] == "R0"
    assert result.set_index("grid_id").loc["IN2", "population"] != result.set_index("grid_id").loc["IN2", "population"]
    assert result.set_index("grid_id").loc["IN1", "population"] == 0
    assert (result["grid_area_m2"] > 0).all()
    assert (result["analysis_area_m2"] > 0).all()
    assert (result["analysis_area_m2"] <= result["grid_area_m2"] + 1e-6).all()
    assert report["raw_grid_count"] == 3 and report["final_grid_count"] == 2


def test_grid_outputs_have_matching_ids_and_geojson_crs(tmp_path):
    grid = gpd.GeoDataFrame(
        {"grid_id": ["G1"], "region_code": ["R1"], "region_name": ["One"], "population": [None], "grid_area_m2": [250000], "analysis_area_m2": [250000], "centroid_x": [250], "centroid_y": [250], "longitude": [127.0], "latitude": [35.0]},
        geometry=[box(0, 0, 500, 500)], crs="EPSG:5179",
    )
    write_hapcheon_grid(grid, tmp_path)
    csv = pd.read_csv(tmp_path / "hapcheon_grid_500m.csv")
    geojson = gpd.read_file(tmp_path / "hapcheon_grid_500m.geojson")
    assert set(csv["grid_id"]) == set(geojson["grid_id"])
    assert geojson.crs.to_epsg() == 4326
