"""Generate the synthetic Analysis Result v0.1 sample from production logic."""

from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import pandas as pd

from gis.build_shelter_accessibility import calculate_shelter_accessibility
from integration.placement_risk import simulate_placement_risk


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = ROOT / "data" / "sample" / "placement_risk_result_v0_1.json"
ORIGIN_X = 1_000_000
ORIGIN_Y = 1_800_000


def _to_wgs84(x: float, y: float = ORIGIN_Y) -> tuple[float, float]:
    point = gpd.GeoSeries(gpd.points_from_xy([x], [y]), crs="EPSG:5179").to_crs(
        "EPSG:4326"
    ).iloc[0]
    return float(point.x), float(point.y)


def build_sample_result() -> dict[str, object]:
    """Run a small synthetic scenario that demonstrates a real threshold crossing."""
    grids = pd.DataFrame(
        {
            "grid_id": ["G-REF", "G-TARGET"],
            "centroid_x": [ORIGIN_X, ORIGIN_X + 1000],
            "centroid_y": [ORIGIN_Y, ORIGIN_Y],
            "elderly_population": [10, 20],
            "grid_area_m2": [250000, 250000],
        }
    )
    shelter_longitude, shelter_latitude = _to_wgs84(ORIGIN_X)
    existing_shelters = pd.DataFrame(
        {
            "shelter_id": ["S-EXISTING"],
            "latitude": [shelter_latitude],
            "longitude": [shelter_longitude],
            "geocoding_status": ["OK"],
        }
    )
    baseline_accessibility = calculate_shelter_accessibility(grids, existing_shelters)

    component_score = 80.0
    baseline_analysis = []
    for grid_id, coverage_gap_score in (("G-REF", 0.0), ("G-TARGET", 100.0)):
        baseline_analysis.append(
            {
                "grid_id": grid_id,
                "analysis_status": "OK",
                "heat_score": component_score,
                "elderly_score": component_score,
                "farmland_score": component_score,
                "coverage_gap_score": coverage_gap_score,
                "vulnerability_score": component_score,
                "risk_level": "VERY_HIGH",
                "installation_need_score": round(
                    component_score * 0.75 + coverage_gap_score * 0.25, 2
                ),
            }
        )

    placement_longitude, placement_latitude = _to_wgs84(ORIGIN_X + 1000)
    placements = [
        {
            "placement_id": "P-TARGET",
            "latitude": placement_latitude,
            "longitude": placement_longitude,
        }
    ]
    return simulate_placement_risk(
        grids,
        baseline_analysis,
        baseline_accessibility,
        existing_shelters,
        placements,
    )


def main() -> None:
    result = build_sample_result()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(OUTPUT_PATH)


if __name__ == "__main__":
    main()
