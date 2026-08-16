"""Assemble processed GIS outputs into a weather-independent AI grid input."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from ai.config import REQUIRED_FEATURES


ROOT = Path(__file__).resolve().parents[1]
GIS_DIR = ROOT / "data" / "processed" / "gis"
OUTPUT_PATH = ROOT / "data" / "processed" / "integration" / "hapcheon_ai_grid_features.csv"

BASE_GRID_PATH = GIS_DIR / "hapcheon_grid_500m.csv"
SHELTER_PATH = GIS_DIR / "hapcheon_grid_shelter_accessibility.csv"
FARMLAND_PATH = GIS_DIR / "hapcheon_grid_farmland.csv"
ELDERLY_PATH = GIS_DIR / "hapcheon_grid_elderly.csv"
BASE_FIELDS = ["grid_id", "region_code", "region_name", "grid_area_m2", "analysis_area_m2", "centroid_x", "centroid_y", "longitude", "latitude"]


def _read_unique(path: Path, required: set[str]) -> pd.DataFrame:
    data = pd.read_csv(path, dtype={"grid_id": "string"})
    if not required.issubset(data.columns):
        raise ValueError(f"{path.name} is missing required fields")
    if data["grid_id"].isna().any() or data["grid_id"].duplicated().any():
        raise ValueError(f"{path.name} grid_id must be unique and non-null")
    return data


def assemble_ai_grid_features(
    base: pd.DataFrame, shelter: pd.DataFrame, farmland: pd.DataFrame, elderly: pd.DataFrame
) -> tuple[pd.DataFrame, dict[str, object]]:
    """LEFT JOIN GIS feature outputs while preserving missing values exactly."""
    base_required = {"grid_id", "region_code", "region_name", "grid_area_m2", "analysis_area_m2", "centroid_x", "centroid_y", "longitude", "latitude"}
    shelter_required = {"grid_id", "nearest_shelter_distance_m", "current_covered"}
    farmland_required = {"grid_id", "farmland_area_m2", "farmland_ratio"}
    elderly_required = {"grid_id", "population", "elderly_population", "elderly_ratio"}
    for name, data, required in (("base", base, base_required), ("shelter", shelter, shelter_required), ("farmland", farmland, farmland_required), ("elderly", elderly, elderly_required)):
        if not required.issubset(data.columns) or data["grid_id"].isna().any() or data["grid_id"].duplicated().any():
            raise ValueError(f"{name} grid input is invalid")

    base_data = base[BASE_FIELDS].copy()
    # Never carry the legacy SGIS base `population` field into the final name.
    shelter_data = shelter[["grid_id", "nearest_shelter_distance_m", "current_covered"]].copy()
    farmland_data = farmland[["grid_id", "farmland_area_m2", "farmland_ratio"]].copy()
    elderly_data = elderly[["grid_id", "population", "elderly_population", "elderly_ratio"]].copy()
    base_ids = set(base_data["grid_id"])
    result = base_data.merge(shelter_data, on="grid_id", how="left", validate="one_to_one")
    result = result.merge(farmland_data, on="grid_id", how="left", validate="one_to_one")
    result = result.merge(elderly_data, on="grid_id", how="left", validate="one_to_one")
    if len(result) != len(base_data) or result["grid_id"].duplicated().any():
        raise ValueError("LEFT JOIN did not preserve the base grid")
    result = result.sort_values("grid_id").reset_index(drop=True)
    required_spatial = [field for field in REQUIRED_FEATURES if field not in {"temperature", "humidity"}]
    missing_by_field = {field: int(result[field].isna().sum()) for field in required_spatial}
    report = {
        "base_grid_count": len(base_data),
        "shelter_unmatched_count": len(base_ids - set(shelter_data["grid_id"])),
        "farmland_unmatched_count": len(base_ids - set(farmland_data["grid_id"])),
        "elderly_unmatched_count": len(base_ids - set(elderly_data["grid_id"])),
        "elderly_ratio_missing_count": int(result["elderly_ratio"].isna().sum()),
        "required_external_fields": list(REQUIRED_FEATURES),
        "required_spatial_fields": required_spatial,
        "missing_by_spatial_field": missing_by_field,
        "spatial_feature_complete_count": int(result[required_spatial].notna().all(axis=1).sum()),
    }
    return result, report


def build_ai_grid_features() -> tuple[pd.DataFrame, dict[str, object]]:
    base = _read_unique(BASE_GRID_PATH, {"grid_id", "region_code", "region_name", "grid_area_m2", "analysis_area_m2", "centroid_x", "centroid_y", "longitude", "latitude"})
    shelter = _read_unique(SHELTER_PATH, {"grid_id", "nearest_shelter_distance_m", "current_covered"})
    farmland = _read_unique(FARMLAND_PATH, {"grid_id", "farmland_area_m2", "farmland_ratio"})
    elderly = _read_unique(ELDERLY_PATH, {"grid_id", "population", "elderly_population", "elderly_ratio"})
    return assemble_ai_grid_features(base, shelter, farmland, elderly)


def write_ai_grid_features(data: pd.DataFrame, output_path: Path = OUTPUT_PATH) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    data.to_csv(output_path, index=False, encoding="utf-8")


def main() -> None:
    data, report = build_ai_grid_features()
    write_ai_grid_features(data)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
