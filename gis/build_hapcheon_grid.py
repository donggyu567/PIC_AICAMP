"""Build centroid-selected Hapcheon SGIS 500m grid outputs.

Inputs are raw boundary/grid ZIP files and a population CSV. Geometry and
area operations use EPSG:5179; the GeoJSON output is transformed to EPSG:4326.
"""

import json
import tempfile
import zipfile
from pathlib import Path
from typing import Any

import geopandas as gpd
import pandas as pd

from .config import ANALYSIS_CRS, API_CRS, AREA_TOLERANCE_M2, BOUNDARY_ZIP, GRID_CSV, GRID_GEOJSON, GRID_ZIP, POPULATION_CSV, PROCESSED_DIR


def read_zipped_shapefile(path: Path) -> gpd.GeoDataFrame:
    """Read a ZIP containing a Shapefile, including nested directory archives."""
    with tempfile.TemporaryDirectory() as temporary_dir:
        with zipfile.ZipFile(path) as archive:
            archive.extractall(temporary_dir)
        shapefiles = sorted(Path(temporary_dir).rglob("*.shp"))
        if len(shapefiles) != 1:
            raise ValueError(f"expected exactly one Shapefile in {path.name}")
        return gpd.read_file(shapefiles[0])


def load_hapcheon_boundaries(path: Path = BOUNDARY_ZIP) -> gpd.GeoDataFrame:
    """Load legal 읍면 boundaries and normalize them for spatial processing."""
    boundaries = read_zipped_shapefile(path)
    if boundaries.crs is None:
        raise ValueError("boundary CRS is missing")
    boundaries = boundaries.to_crs(ANALYSIS_CRS)
    if not boundaries.is_valid.all():
        boundaries = boundaries.copy()
        boundaries.geometry = boundaries.geometry.make_valid()
    result = boundaries[["A1", "A2", "geometry"]].rename(columns={"A1": "region_code", "A2": "region_name"})
    if result["region_code"].isna().any() or result["region_code"].duplicated().any() or len(result) != 17:
        raise ValueError("expected 17 unique non-null legal 읍면 region codes")
    return result


def build_hapcheon_grid(
    boundary_path: Path = BOUNDARY_ZIP,
    grid_path: Path = GRID_ZIP,
    population_path: Path = POPULATION_CSV,
) -> tuple[gpd.GeoDataFrame, dict[str, int]]:
    """Return final centroid-selected grid GeoDataFrame and validation counts."""
    boundaries = load_hapcheon_boundaries(boundary_path)
    county_geometry = boundaries.union_all()
    raw_grids = read_zipped_shapefile(grid_path)
    if raw_grids.crs is None:
        raise ValueError("grid CRS is missing")
    raw_grids = raw_grids.to_crs(ANALYSIS_CRS)
    if not raw_grids.is_valid.all():
        raw_grids = raw_grids.copy()
        raw_grids.geometry = raw_grids.geometry.make_valid()
    grids = raw_grids[["GRID_CD", "geometry"]].rename(columns={"GRID_CD": "grid_id"}).copy()
    if grids["grid_id"].isna().any() or grids["grid_id"].duplicated().any():
        raise ValueError("raw grid_id must be unique and non-null")
    grids["centroid"] = grids.geometry.centroid
    inside = grids["centroid"].apply(county_geometry.covers)
    final_grids = grids.loc[inside].copy()
    final_grids["grid_area_m2"] = final_grids.geometry.area
    final_grids["analysis_area_m2"] = final_grids.geometry.intersection(county_geometry).area
    if (final_grids["grid_area_m2"] <= 0).any() or (final_grids["analysis_area_m2"] <= 0).any():
        raise ValueError("grid areas must be positive")
    if (final_grids["analysis_area_m2"] > final_grids["grid_area_m2"] + AREA_TOLERANCE_M2).any():
        raise ValueError("analysis area exceeds source grid area")

    centroids = gpd.GeoDataFrame(final_grids[["grid_id"]], geometry=final_grids["centroid"], crs=ANALYSIS_CRS)
    mapped = gpd.sjoin(centroids, boundaries, how="left", predicate="within")
    if mapped["grid_id"].duplicated().any():
        raise ValueError("a grid centroid mapped to multiple legal regions")
    final_grids = final_grids.merge(mapped[["grid_id", "region_code", "region_name"]], on="grid_id", how="left", validate="one_to_one")

    population = pd.read_csv(population_path, dtype={"grid_id": "string"})[["grid_id", "population"]]
    if population["grid_id"].duplicated().any():
        raise ValueError("population grid_id must be unique")
    final_grids = final_grids.merge(population, on="grid_id", how="left", validate="one_to_one")
    final_grids["centroid_x"] = final_grids["centroid"].x
    final_grids["centroid_y"] = final_grids["centroid"].y
    geographic_centroids = gpd.GeoSeries(final_grids["centroid"], crs=ANALYSIS_CRS).to_crs(API_CRS)
    final_grids["longitude"] = geographic_centroids.x
    final_grids["latitude"] = geographic_centroids.y
    final_grids = final_grids.drop(columns="centroid").sort_values("grid_id").reset_index(drop=True)
    report = {
        "raw_grid_count": len(raw_grids), "final_grid_count": len(final_grids),
        "region_code_null_count": int(final_grids["region_code"].isna().sum()),
        "region_name_null_count": int(final_grids["region_name"].isna().sum()),
        "population_present_count": int(final_grids["population"].notna().sum()),
        "population_null_count": int(final_grids["population"].isna().sum()),
        "boundary_region_count": len(boundaries),
    }
    return final_grids, report


def write_hapcheon_grid(grid: gpd.GeoDataFrame, output_dir: Path = PROCESSED_DIR) -> None:
    """Write deterministic CSV and EPSG:4326 GeoJSON grid artifacts."""
    output_dir.mkdir(parents=True, exist_ok=True)
    fields = ["grid_id", "region_code", "region_name", "population", "grid_area_m2", "analysis_area_m2", "centroid_x", "centroid_y", "longitude", "latitude"]
    grid[fields].to_csv(output_dir / GRID_CSV.name, index=False, encoding="utf-8")
    grid[fields + ["geometry"]].to_crs(API_CRS).to_file(output_dir / GRID_GEOJSON.name, driver="GeoJSON", index=False)


def main() -> None:
    grid, report = build_hapcheon_grid()
    write_hapcheon_grid(grid)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
