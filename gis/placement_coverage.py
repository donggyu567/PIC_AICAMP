"""Runtime coverage wrapper for user-selected WGS84 placement points.

The wrapper intentionally reuses the Candidate Coverage pipeline's final-grid
centroids and 300-metre EPSG:5179 distance operation.  It does not perform
candidate selection or any AI calculation.
"""

from __future__ import annotations

from functools import lru_cache
import math
from pathlib import Path
from typing import Any, Iterable, Mapping

import geopandas as gpd

from .build_candidate_coverage import load_final_grid_centroids, map_points_to_covered_grid_ids
from .config import ANALYSIS_CRS, API_CRS, GRID_GEOJSON


def build_placement_coverage(
    placements: Iterable[Mapping[str, Any]],
    grid_geojson_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Return sorted 300m centroid coverage for each user placement.

    The returned list preserves the input placement order.  An otherwise valid
    point outside every final-grid radius is represented by an empty list.
    """
    records = _validate_placements(placements)
    if not records:
        return []
    points = gpd.GeoDataFrame(
        records,
        geometry=gpd.points_from_xy(
            [record["longitude"] for record in records],
            [record["latitude"] for record in records],
        ),
        crs=API_CRS,
    ).to_crs(ANALYSIS_CRS)
    centroids = (
        _default_grid_centroids()
        if grid_geojson_path is None
        else load_final_grid_centroids(grid_geojson_path)
    )
    covered_by_id = map_points_to_covered_grid_ids(points, "placement_id", centroids)
    return [
        {
            "placement_id": record["placement_id"],
            "latitude": record["latitude"],
            "longitude": record["longitude"],
            "covered_grid_ids": covered_by_id.get(record["placement_id"], []),
        }
        for record in records
    ]


@lru_cache(maxsize=1)
def _default_grid_centroids() -> gpd.GeoDataFrame:
    """Cache only the fixed processed final-grid centroids for runtime calls."""
    return load_final_grid_centroids(GRID_GEOJSON)


def _validate_placements(placements: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    if isinstance(placements, (str, bytes)):
        raise ValueError("placements must be an iterable of mappings")
    try:
        iterator = iter(placements)
    except TypeError as exc:
        raise ValueError("placements must be an iterable of mappings") from exc
    records: list[dict[str, Any]] = []
    placement_ids: set[str] = set()
    for placement in iterator:
        if not isinstance(placement, Mapping):
            raise ValueError("each placement must be a mapping")
        placement_id = placement.get("placement_id")
        if not isinstance(placement_id, str) or not placement_id:
            raise ValueError("placement_id must be a non-empty string")
        if placement_id in placement_ids:
            raise ValueError("placement_id must be unique and non-null")
        latitude = _coordinate(placement.get("latitude"), "latitude", -90, 90)
        longitude = _coordinate(placement.get("longitude"), "longitude", -180, 180)
        placement_ids.add(placement_id)
        records.append(
            {
                "placement_id": placement_id,
                "latitude": latitude,
                "longitude": longitude,
            }
        )
    return records


def _coordinate(value: Any, name: str, lower: float, upper: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be numeric and in WGS84 range")
    numeric = float(value)
    if not math.isfinite(numeric) or not lower <= numeric <= upper:
        raise ValueError(f"{name} must be numeric and in WGS84 range")
    return numeric
