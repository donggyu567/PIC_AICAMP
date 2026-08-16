"""Build unique P0 farmland area and ratio for the established Hapcheon grids."""

from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import pandas as pd

from .build_hapcheon_grid import load_hapcheon_boundaries, read_zipped_shapefile
from .config import (
    ANALYSIS_CRS,
    AREA_TOLERANCE_M2,
    FARMLAND_CODE_COLUMN,
    FARMLAND_CODES,
    FARMMAP_ZIP,
    GRID_CSV,
    GRID_FARMLAND_CSV,
    GRID_ZIP,
    NON_FARMLAND_CODES,
    PROCESSED_DIR,
)


def load_final_grid_geometries(
    grid_csv_path: Path = GRID_CSV, grid_zip_path: Path = GRID_ZIP
) -> gpd.GeoDataFrame:
    """Return the already-selected 3,934 grid polygons clipped to the county boundary."""
    grid_attributes = pd.read_csv(grid_csv_path, dtype={"grid_id": "string"})
    required = {"grid_id", "analysis_area_m2"}
    if not required.issubset(grid_attributes.columns):
        raise ValueError("final grid CSV is missing grid_id or analysis_area_m2")
    if grid_attributes["grid_id"].isna().any() or grid_attributes["grid_id"].duplicated().any():
        raise ValueError("final grid_id must be unique and non-null")
    grid_attributes["analysis_area_m2"] = pd.to_numeric(grid_attributes["analysis_area_m2"], errors="coerce")
    if grid_attributes["analysis_area_m2"].isna().any() or (grid_attributes["analysis_area_m2"] <= 0).any():
        raise ValueError("analysis_area_m2 must be positive and non-null")
    raw_grids = read_zipped_shapefile(grid_zip_path)
    if raw_grids.crs is None:
        raise ValueError("raw grid CRS is missing")
    raw_grids = raw_grids.to_crs(ANALYSIS_CRS)
    geometries = raw_grids[["GRID_CD", "geometry"]].rename(columns={"GRID_CD": "grid_id"})
    geometries["grid_id"] = geometries["grid_id"].astype("string")
    selected = geometries[geometries["grid_id"].isin(grid_attributes["grid_id"])].copy()
    if len(selected) != len(grid_attributes) or selected["grid_id"].duplicated().any():
        raise ValueError("raw grid geometry does not match final grid_id set")
    county_geometry = load_hapcheon_boundaries().union_all()
    selected["geometry"] = selected.geometry.intersection(county_geometry)
    if selected.geometry.is_empty.any():
        raise ValueError("final grid geometry is empty after county clipping")
    result = selected.merge(grid_attributes[["grid_id", "analysis_area_m2"]], on="grid_id", how="inner", validate="one_to_one")
    return gpd.GeoDataFrame(result, geometry="geometry", crs=ANALYSIS_CRS).sort_values("grid_id").reset_index(drop=True)


def load_farmmap(path: Path = FARMMAP_ZIP) -> tuple[gpd.GeoDataFrame, dict[str, object]]:
    """Load Farm Map with source CRS validation and minimally repair invalid geometries."""
    farmmap = read_zipped_shapefile(path)
    if farmmap.crs is None:
        raise ValueError("Farm Map CRS is missing")
    if FARMLAND_CODE_COLUMN not in farmmap.columns:
        raise ValueError(f"Farm Map is missing {FARMLAND_CODE_COLUMN}")
    farmmap = farmmap.to_crs(ANALYSIS_CRS).copy()
    farmmap[FARMLAND_CODE_COLUMN] = farmmap[FARMLAND_CODE_COLUMN].astype("string")
    invalid_before = int((~farmmap.geometry.is_valid).sum())
    if invalid_before:
        farmmap.geometry = farmmap.geometry.make_valid()
    invalid_after = int((~farmmap.geometry.is_valid).sum())
    empty_after = int(farmmap.geometry.is_empty.sum())
    code_counts = farmmap[FARMLAND_CODE_COLUMN].value_counts(dropna=False).to_dict()
    return farmmap, {
        "farmmap_row_count": len(farmmap), "farmmap_crs": str(farmmap.crs),
        "invalid_geometry_before": invalid_before, "invalid_geometry_after": invalid_after,
        "empty_geometry_count": empty_after, "code_counts": {str(key): int(value) for key, value in code_counts.items()},
    }


def calculate_farmland_features(
    grids: gpd.GeoDataFrame, farmmap: gpd.GeoDataFrame, code_column: str = FARMLAND_CODE_COLUMN
) -> tuple[pd.DataFrame, dict[str, object]]:
    """Calculate per-grid unique 01/02/03/04 Farm Map area in EPSG:5179.

    ``analysis_area_m2`` originates from the established grid CSV and remains the
    ratio denominator. Farm polygons are unioned inside each grid after overlay,
    preventing overlapping Farm Map polygons from being double counted.
    """
    required_grid = {"grid_id", "analysis_area_m2", "geometry"}
    if not required_grid.issubset(grids.columns):
        raise ValueError("grid input is missing required fields")
    if code_column not in farmmap.columns:
        raise ValueError(f"Farm Map is missing {code_column}")
    if grids.crs is None or farmmap.crs is None:
        raise ValueError("grid and Farm Map CRS are required")
    grid_data = grids[["grid_id", "analysis_area_m2", "geometry"]].copy().to_crs(ANALYSIS_CRS)
    if grid_data["grid_id"].isna().any() or grid_data["grid_id"].duplicated().any():
        raise ValueError("grid_id must be unique and non-null")
    grid_data["analysis_area_m2"] = pd.to_numeric(grid_data["analysis_area_m2"], errors="coerce")
    if grid_data["analysis_area_m2"].isna().any() or (grid_data["analysis_area_m2"] <= 0).any():
        raise ValueError("analysis_area_m2 must be positive and non-null")
    if grid_data.geometry.is_empty.any():
        raise ValueError("grid geometry must not be empty")

    farm_data = farmmap[[code_column, "geometry"]].copy().to_crs(ANALYSIS_CRS)
    farm_data[code_column] = farm_data[code_column].astype("string")
    invalid_before = int((~farm_data.geometry.is_valid).sum())
    if invalid_before:
        farm_data.geometry = farm_data.geometry.make_valid()
    invalid_after = int((~farm_data.geometry.is_valid).sum())
    empty_count = int(farm_data.geometry.is_empty.sum())
    known_codes = FARMLAND_CODES | NON_FARMLAND_CODES
    unknown = farm_data.loc[~farm_data[code_column].isin(known_codes), code_column].value_counts(dropna=False)
    farmland = farm_data.loc[farm_data[code_column].isin(FARMLAND_CODES) & ~farm_data.geometry.is_empty].copy()
    code_counts = farm_data[code_column].value_counts(dropna=False).to_dict()

    if farmland.empty:
        unique_areas = pd.Series(dtype="float64")
        raw_area_total = 0.0
    else:
        intersections = gpd.overlay(grid_data[["grid_id", "geometry"]], farmland[["geometry"]], how="intersection", keep_geom_type=False)
        intersections = intersections.loc[~intersections.geometry.is_empty].copy()
        raw_area_total = float(intersections.geometry.area.sum())
        unique_areas = intersections.groupby("grid_id").geometry.agg(lambda geometries: geometries.union_all().area)
    result = grid_data[["grid_id", "analysis_area_m2"]].copy()
    result["farmland_area_m2"] = result["grid_id"].map(unique_areas).fillna(0.0)
    excess = result["farmland_area_m2"] - result["analysis_area_m2"]
    tolerance_clamp_count = int(((excess > 0) & (excess <= AREA_TOLERANCE_M2)).sum())
    if tolerance_clamp_count:
        result.loc[(excess > 0) & (excess <= AREA_TOLERANCE_M2), "farmland_area_m2"] = result.loc[(excess > 0) & (excess <= AREA_TOLERANCE_M2), "analysis_area_m2"]
    material_excess_count = int((result["farmland_area_m2"] > result["analysis_area_m2"] + AREA_TOLERANCE_M2).sum())
    if material_excess_count:
        raise ValueError("farmland area materially exceeds analysis_area_m2")
    result["farmland_ratio"] = result["farmland_area_m2"] / result["analysis_area_m2"]
    overlap_area_m2 = raw_area_total - float(result["farmland_area_m2"].sum())
    report = {
        "code_counts": {str(key): int(value) for key, value in code_counts.items()},
        "unknown_code_counts": {str(key): int(value) for key, value in unknown.to_dict().items()},
        "invalid_geometry_before": invalid_before, "invalid_geometry_after": invalid_after,
        "empty_geometry_count": empty_count, "intersection_overlap_detected": overlap_area_m2 > AREA_TOLERANCE_M2,
        "raw_intersection_area_m2": raw_area_total, "total_farmland_area_m2": float(result["farmland_area_m2"].sum()),
        "overlap_area_removed_m2": overlap_area_m2, "tolerance_clamp_count": tolerance_clamp_count,
        "material_excess_count": material_excess_count,
    }
    return result.sort_values("grid_id").reset_index(drop=True), report


def build_farmland_features() -> tuple[pd.DataFrame, dict[str, object]]:
    grids = load_final_grid_geometries()
    farmmap, farmmap_report = load_farmmap()
    result, calculation_report = calculate_farmland_features(grids, farmmap)
    return result, {**farmmap_report, **calculation_report, "grid_count": len(result)}


def write_farmland_features(data: pd.DataFrame, output_dir: Path = PROCESSED_DIR) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    data[["grid_id", "farmland_area_m2", "farmland_ratio", "analysis_area_m2"]].to_csv(
        output_dir / GRID_FARMLAND_CSV.name, index=False, encoding="utf-8"
    )


def main() -> None:
    data, report = build_farmland_features()
    write_farmland_features(data)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
