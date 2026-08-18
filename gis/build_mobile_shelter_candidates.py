"""Build mobile-shelter installation candidates from analyzed blind-spot grids."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import geopandas as gpd
import pandas as pd

from .build_candidate_coverage import (
    load_final_grid_centroids,
    map_points_to_covered_grid_ids,
)
from .config import (
    ANALYSIS_CRS,
    API_CRS,
    GRID_GEOJSON,
    MOBILE_SHELTER_CANDIDATE_COVERAGE_JSON,
)


ROOT = Path(__file__).resolve().parents[1]
GRID_FEATURES_PATH = ROOT / "data" / "processed" / "integration" / "hapcheon_ai_grid_features.csv"
ANALYSIS_PATH = ROOT / "data" / "processed" / "analysis" / "hapcheon_ai_analysis.csv"

CANDIDATE_TYPE = "이동식쉼터_설치검토지점"
OUTPUT_FIELDS = [
    "candidate_id",
    "candidate_name",
    "candidate_type",
    "region_code",
    "region_name",
    "latitude",
    "longitude",
    "covered_grid_ids",
]


def build_mobile_shelter_candidates(
    grid_features: pd.DataFrame,
    analysis_results: pd.DataFrame,
    grid_geojson_path: Path = GRID_GEOJSON,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Return one candidate for every uncovered blind-spot grid centroid.

    Candidate eligibility comes only from the existing analysis result. Spatial
    coverage is delegated to the same 300m GIS helper used by legacy candidate
    facilities; no facility type is reclassified as an official shelter.
    """
    _validate_source(
        grid_features,
        "grid features",
        {
            "grid_id", "region_code", "region_name", "current_covered",
            "latitude", "longitude",
        },
    )
    _validate_source(
        analysis_results,
        "analysis results",
        {"grid_id", "blind_spot"},
    )
    if set(grid_features["grid_id"]) != set(analysis_results["grid_id"]):
        raise ValueError("grid feature and analysis grid_ids must match")

    source = grid_features[
        [
            "grid_id", "region_code", "region_name", "current_covered",
            "latitude", "longitude",
        ]
    ].merge(
        analysis_results[["grid_id", "blind_spot"]],
        on="grid_id",
        how="left",
        validate="one_to_one",
    )
    targets = source.loc[
        source["current_covered"].eq(False) & source["blind_spot"].eq(True)
    ].sort_values("grid_id", kind="mergesort")

    centroids = load_final_grid_centroids(grid_geojson_path)
    centroid_ids = set(centroids["grid_id"])
    missing_centroids = set(targets["grid_id"]) - centroid_ids
    if missing_centroids:
        raise ValueError(f"eligible grid is missing a centroid: {sorted(missing_centroids)[0]}")

    points = targets.copy()
    for field, lower, upper in (("latitude", -90, 90), ("longitude", -180, 180)):
        points[field] = pd.to_numeric(points[field], errors="coerce")
        if points[field].isna().any() or not points[field].between(lower, upper).all():
            raise ValueError(f"eligible grid {field} must be numeric and in WGS84 range")
    points = gpd.GeoDataFrame(
        points,
        geometry=gpd.points_from_xy(points["longitude"], points["latitude"]),
        crs=API_CRS,
    ).to_crs(ANALYSIS_CRS)
    points["candidate_id"] = points["grid_id"].map(lambda grid_id: f"MOBILE_{grid_id}")
    points["candidate_name"] = [
        f"신규 이동식 쉼터 후보 {position}" for position in range(1, len(points) + 1)
    ]
    points["candidate_type"] = CANDIDATE_TYPE

    coverage = map_points_to_covered_grid_ids(points, "candidate_id", centroids)
    points["covered_grid_ids"] = points["candidate_id"].map(
        lambda candidate_id: coverage.get(candidate_id, [])
    )
    result = pd.DataFrame(points.drop(columns=["geometry", "grid_id", "current_covered", "blind_spot"]))
    result = result[OUTPUT_FIELDS].reset_index(drop=True)

    report = {
        "candidate_count": len(result),
        "candidate_id_duplicate_count": int(result["candidate_id"].duplicated().sum()),
        "coordinate_null_count": int(result[["latitude", "longitude"]].isna().any(axis=1).sum()),
        "empty_coverage_candidate_count": int((~result["covered_grid_ids"].map(bool)).sum()),
        "source_uncovered_count": int(targets["current_covered"].eq(False).sum()),
        "source_blind_spot_count": int(targets["blind_spot"].eq(True).sum()),
    }
    return result, report


def _validate_source(data: pd.DataFrame, name: str, required: set[str]) -> None:
    if not required.issubset(data.columns):
        raise ValueError(f"{name} is missing required fields")
    if data["grid_id"].isna().any() or data["grid_id"].duplicated().any():
        raise ValueError(f"{name} grid_id must be unique and non-null")


def write_mobile_shelter_candidates(
    candidates: pd.DataFrame,
    output_path: Path = MOBILE_SHELTER_CANDIDATE_COVERAGE_JSON,
) -> None:
    """Write the Backend-compatible candidate JSON without touching legacy data."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(candidates.to_dict("records"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> None:
    grid_features = pd.read_csv(
        GRID_FEATURES_PATH,
        dtype={"grid_id": "string", "region_code": "string"},
    )
    analysis_results = pd.read_csv(ANALYSIS_PATH, dtype={"grid_id": "string"})
    candidates, report = build_mobile_shelter_candidates(grid_features, analysis_results)
    write_mobile_shelter_candidates(candidates)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
