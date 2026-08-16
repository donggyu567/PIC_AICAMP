"""Calculate 300m fixed-shelter accessibility from valid geocoded points."""

from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import pandas as pd

from .config import ANALYSIS_CRS, API_CRS, GRID_CSV, GRID_SHELTER_ACCESSIBILITY_CSV, PROCESSED_DIR, SHELTER_GEOCODED_CSV, SHELTER_SERVICE_RADIUS_M


def build_shelter_accessibility(
    grid_path: Path = GRID_CSV, shelters_path: Path = SHELTER_GEOCODED_CSV
) -> tuple[pd.DataFrame, dict[str, object]]:
    """Return one row per grid without modifying either input file."""
    grids = pd.read_csv(grid_path, dtype={"grid_id": "string"})
    required_grid_fields = {"grid_id", "centroid_x", "centroid_y"}
    if not required_grid_fields.issubset(grids.columns) or grids["grid_id"].isna().any() or grids["grid_id"].duplicated().any():
        raise ValueError("grid input must have unique non-null grid_id and centroid coordinates")
    for field in ("centroid_x", "centroid_y"):
        grids[field] = pd.to_numeric(grids[field], errors="coerce")
        if grids[field].isna().any():
            raise ValueError(f"grid {field} must be numeric")
    shelters = pd.read_csv(shelters_path, dtype={"shelter_id": "string"})
    required_shelter_fields = {"shelter_id", "latitude", "longitude", "geocoding_status"}
    if not required_shelter_fields.issubset(shelters.columns) or shelters["shelter_id"].isna().any() or shelters["shelter_id"].duplicated().any():
        raise ValueError("shelter input must have unique non-null shelter_id and geocoding fields")
    valid = shelters["geocoding_status"].eq("OK").copy()
    for field, lower, upper in (("latitude", -90, 90), ("longitude", -180, 180)):
        shelters[field] = pd.to_numeric(shelters[field], errors="coerce")
        valid &= shelters[field].between(lower, upper)
    grid_points = gpd.GeoDataFrame(grids[["grid_id"]], geometry=gpd.points_from_xy(grids.centroid_x, grids.centroid_y), crs=ANALYSIS_CRS)
    result = grids[["grid_id"]].copy()
    if not valid.any():
        result["nearest_shelter_distance_m"] = pd.Series(pd.NA, index=result.index, dtype="Float64")
        result["current_covered"] = pd.Series(pd.NA, index=result.index, dtype="boolean")
        result["shelter_count"] = pd.Series(pd.NA, index=result.index, dtype="Int64")
    else:
        shelter_points = gpd.GeoDataFrame(shelters.loc[valid, ["shelter_id"]], geometry=gpd.points_from_xy(shelters.loc[valid, "longitude"], shelters.loc[valid, "latitude"]), crs=API_CRS).to_crs(ANALYSIS_CRS)
        nearest = gpd.sjoin_nearest(grid_points, shelter_points, how="left", distance_col="nearest_shelter_distance_m")
        nearest = nearest.sort_values(["grid_id", "nearest_shelter_distance_m", "shelter_id"]).drop_duplicates("grid_id")
        result = result.merge(nearest[["grid_id", "shelter_id", "nearest_shelter_distance_m"]], on="grid_id", how="left", validate="one_to_one").rename(columns={"shelter_id": "nearest_shelter_id"})
        result["current_covered"] = result["nearest_shelter_distance_m"].le(SHELTER_SERVICE_RADIUS_M).astype("boolean")
        joined = gpd.sjoin(grid_points, shelter_points, how="left", predicate="dwithin", distance=SHELTER_SERVICE_RADIUS_M)
        counts = joined.dropna(subset="shelter_id").groupby("grid_id")["shelter_id"].nunique()
        result["shelter_count"] = result["grid_id"].map(counts).fillna(0).astype("Int64")
    distances = result["nearest_shelter_distance_m"].dropna()
    report = {
        "grid_count": len(result), "valid_geocoded_count": int(valid.sum()),
        "current_covered_true_count": int(result["current_covered"].eq(True).sum()),
        "current_covered_false_count": int(result["current_covered"].eq(False).sum()),
        "current_covered_null_count": int(result["current_covered"].isna().sum()),
        "shelter_count_min": None if result["shelter_count"].isna().all() else int(result["shelter_count"].min()),
        "shelter_count_max": None if result["shelter_count"].isna().all() else int(result["shelter_count"].max()),
        "nearest_distance_min_m": None if distances.empty else float(distances.min()),
        "nearest_distance_max_m": None if distances.empty else float(distances.max()),
        "nearest_distance_median_m": None if distances.empty else float(distances.median()),
    }
    return result.sort_values("grid_id").reset_index(drop=True), report


def write_shelter_accessibility(data: pd.DataFrame, output_dir: Path = PROCESSED_DIR) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    data.to_csv(output_dir / GRID_SHELTER_ACCESSIBILITY_CSV.name, index=False, encoding="utf-8")


def main() -> None:
    data, report = build_shelter_accessibility()
    write_shelter_accessibility(data)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
