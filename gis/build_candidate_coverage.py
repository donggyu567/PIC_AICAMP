"""Build deterministic Candidate-to-grid-centroid coverage at 300 metres."""

import json
from pathlib import Path
from typing import Any, Mapping

import geopandas as gpd
import pandas as pd

from .build_hapcheon_grid import load_hapcheon_boundaries
from .config import ANALYSIS_CRS, CANDIDATE_COVERAGE_CSV, CANDIDATE_COVERAGE_JSON, CANDIDATES_CSV, COVERAGE_DISTANCE_M, GRID_GEOJSON, PROCESSED_DIR


def build_candidate_coverage(
    grid_geojson_path: Path = GRID_GEOJSON,
    candidates_path: Path = CANDIDATES_CSV,
    boundaries: gpd.GeoDataFrame | None = None,
) -> tuple[pd.DataFrame, dict[str, int]]:
    """Return candidates with GIS-supplied 300m centroid coverage lists."""
    centroids = load_final_grid_centroids(grid_geojson_path)
    candidates = pd.read_csv(candidates_path, dtype={"candidate_id": "string"})
    _validate_candidates(candidates)
    source_fields = candidates.drop(columns=["region_code", "region_name"], errors="ignore")
    points = gpd.GeoDataFrame(source_fields, geometry=gpd.points_from_xy(candidates.longitude, candidates.latitude), crs="EPSG:4326").to_crs(ANALYSIS_CRS)
    boundary_data = (
        load_hapcheon_boundaries()
        if boundaries is None
        else boundaries.to_crs(ANALYSIS_CRS).copy()
    )
    required_boundary_fields = {"region_code", "region_name", "geometry"}
    if not required_boundary_fields.issubset(boundary_data.columns):
        raise ValueError("boundary input is missing required fields")
    mapped = gpd.sjoin(points[["candidate_id", "geometry"]], boundary_data, how="left", predicate="within")
    if mapped["candidate_id"].duplicated().any():
        raise ValueError("a candidate mapped to multiple legal regions")
    points = points.merge(mapped[["candidate_id", "region_code", "region_name"]], on="candidate_id", how="left")

    coverage = map_points_to_covered_grid_ids(points, "candidate_id", centroids)
    result = points.drop(columns="geometry").copy()
    result["covered_grid_ids"] = result["candidate_id"].map(lambda candidate_id: coverage.get(candidate_id, []))
    result = result[["candidate_id", "candidate_name", "candidate_type", "region_code", "region_name", "latitude", "longitude", "covered_grid_ids"]].sort_values("candidate_id").reset_index(drop=True)
    report = {
        "candidate_count": len(result), "outside_boundary_count": int(result["region_code"].isna().sum()),
        "region_code_null_count": int(result["region_code"].isna().sum()),
        "covered_candidate_count": int(result["covered_grid_ids"].map(bool).sum()),
        "empty_coverage_candidate_count": int((~result["covered_grid_ids"].map(bool)).sum()),
    }
    return result, report


def load_final_grid_centroids(grid_geojson_path: Path = GRID_GEOJSON) -> gpd.GeoDataFrame:
    """Load the fixed final Hapcheon grid and expose its EPSG:5179 centroids."""
    grids = gpd.read_file(grid_geojson_path).to_crs(ANALYSIS_CRS)
    if grids["grid_id"].isna().any() or grids["grid_id"].duplicated().any():
        raise ValueError("final grid_id must be unique and non-null")
    return gpd.GeoDataFrame(
        grids[["grid_id"]], geometry=grids.geometry.centroid, crs=ANALYSIS_CRS
    )


def map_points_to_covered_grid_ids(
    points: gpd.GeoDataFrame,
    point_id_column: str,
    centroids: gpd.GeoDataFrame,
) -> Mapping[str, list[str]]:
    """Map EPSG:5179 points to sorted final-grid IDs within the P0 radius."""
    joined = gpd.sjoin(
        points[[point_id_column, "geometry"]],
        centroids,
        how="left",
        predicate="dwithin",
        distance=COVERAGE_DISTANCE_M,
    )
    return (
        joined.dropna(subset="grid_id")
        .groupby(point_id_column)["grid_id"]
        .agg(lambda ids: sorted(set(ids)))
        .to_dict()
    )


def _validate_candidates(candidates: pd.DataFrame) -> None:
    required = {"candidate_id", "candidate_name", "candidate_type", "latitude", "longitude"}
    if not required.issubset(candidates.columns):
        raise ValueError("candidate input is missing required fields")
    if candidates["candidate_id"].isna().any() or candidates["candidate_id"].duplicated().any():
        raise ValueError("candidate_id must be unique and non-null")
    for field, lower, upper in (("latitude", -90, 90), ("longitude", -180, 180)):
        candidates[field] = pd.to_numeric(candidates[field], errors="coerce")
        if candidates[field].isna().any() or not candidates[field].between(lower, upper).all():
            raise ValueError(f"candidate {field} must be numeric and in WGS84 range")


def write_candidate_coverage(coverage: pd.DataFrame, output_dir: Path = PROCESSED_DIR) -> None:
    """Write JSON-array CSV values plus matching JSON records."""
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_data = coverage.copy()
    csv_data["covered_grid_ids"] = csv_data["covered_grid_ids"].map(lambda ids: json.dumps(ids, ensure_ascii=False, separators=(",", ":")))
    csv_data.to_csv(output_dir / CANDIDATE_COVERAGE_CSV.name, index=False, encoding="utf-8")
    (output_dir / CANDIDATE_COVERAGE_JSON.name).write_text(json.dumps(coverage.to_dict("records"), ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    coverage, report = build_candidate_coverage()
    write_candidate_coverage(coverage)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
