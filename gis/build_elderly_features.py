"""Join NGII 202410 population and elderly values to established Hapcheon grids."""

from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import pandas as pd

from .build_hapcheon_grid import read_zipped_shapefile
from .config import (
    ANALYSIS_CRS,
    ELDERLY_AGE_THRESHOLD,
    GRID_CSV,
    GRID_ELDERLY_CSV,
    GRID_ZIP,
    NGII_GRID_ID_COLUMN,
    NGII_REFERENCE_DATE,
    NGII_VALUE_COLUMN,
    PROCESSED_DIR,
    RAW_DIR,
)


NGII_DIRECTORY = RAW_DIR / "elderly"
ELDERLY_ARCHIVE_PATTERN = "*고령인구*202410.zip"
POPULATION_ARCHIVE_PATTERN = "*총인구*202410.zip"


def find_ngii_archives(directory: Path = NGII_DIRECTORY) -> tuple[Path, Path]:
    """Return the source population and elderly archives without guessing paths."""
    population = sorted(directory.glob(POPULATION_ARCHIVE_PATTERN))
    elderly = sorted(directory.glob(ELDERLY_ARCHIVE_PATTERN))
    if len(population) != 1 or len(elderly) != 1:
        raise ValueError("expected exactly one NGII population and elderly archive")
    return population[0], elderly[0]


def load_ngii_dataset(path: Path) -> tuple[gpd.GeoDataFrame, dict[str, object]]:
    """Load one NGII 500m dataset while retaining missing values as missing."""
    data = read_zipped_shapefile(path)
    required = {NGII_GRID_ID_COLUMN, NGII_VALUE_COLUMN}
    if data.crs is None or not required.issubset(data.columns):
        raise ValueError("NGII dataset is missing CRS, gid, or val")
    data = data.to_crs(ANALYSIS_CRS).copy()
    data[NGII_GRID_ID_COLUMN] = data[NGII_GRID_ID_COLUMN].astype("string")
    if data[NGII_GRID_ID_COLUMN].isna().any() or data[NGII_GRID_ID_COLUMN].duplicated().any():
        raise ValueError("NGII grid ID must be unique and non-null")
    values = pd.to_numeric(data[NGII_VALUE_COLUMN], errors="coerce")
    if (values.dropna() < 0).any():
        raise ValueError("NGII population values must not be negative")
    data[NGII_VALUE_COLUMN] = values
    report = {
        "row_count": len(data), "crs": str(data.crs),
        "invalid_geometry_count": int((~data.geometry.is_valid).sum()),
        "empty_geometry_count": int(data.geometry.is_empty.sum()),
        "grid_id_null_count": int(data[NGII_GRID_ID_COLUMN].isna().sum()),
        "grid_id_duplicate_count": int(data[NGII_GRID_ID_COLUMN].duplicated().sum()),
        "value_null_count": int(values.isna().sum()), "value_zero_count": int(values.eq(0).sum()),
    }
    if report["invalid_geometry_count"] or report["empty_geometry_count"]:
        raise ValueError("NGII geometry must be valid and non-empty")
    return data, report


def validate_ngii_pair(population: gpd.GeoDataFrame, elderly: gpd.GeoDataFrame) -> None:
    """Require identical ID sets and geometry before population/elderly joining."""
    population_ids = set(population[NGII_GRID_ID_COLUMN])
    elderly_ids = set(elderly[NGII_GRID_ID_COLUMN])
    if population_ids != elderly_ids:
        raise ValueError("NGII population and elderly grid ID sets differ")
    paired = population[[NGII_GRID_ID_COLUMN, "geometry"]].merge(
        elderly[[NGII_GRID_ID_COLUMN, "geometry"]], on=NGII_GRID_ID_COLUMN, suffixes=("_population", "_elderly"), validate="one_to_one"
    )
    if any(not left.equals_exact(right, tolerance=0) for left, right in zip(paired.geometry_population, paired.geometry_elderly)):
        raise ValueError("NGII population and elderly geometry differs for the same grid ID")


def load_final_sgis_grid_geometries(grid_csv_path: Path = GRID_CSV, grid_zip_path: Path = GRID_ZIP) -> gpd.GeoDataFrame:
    """Load exactly the established final SGIS grid set, without changing it."""
    attributes = pd.read_csv(grid_csv_path, dtype={"grid_id": "string"})
    if "grid_id" not in attributes or attributes["grid_id"].isna().any() or attributes["grid_id"].duplicated().any():
        raise ValueError("final SGIS grid IDs must be unique and non-null")
    raw = read_zipped_shapefile(grid_zip_path)
    if raw.crs is None:
        raise ValueError("raw SGIS grid CRS is missing")
    raw = raw.to_crs(ANALYSIS_CRS)[["GRID_CD", "geometry"]].rename(columns={"GRID_CD": "grid_id"})
    raw["grid_id"] = raw["grid_id"].astype("string")
    final = raw[raw["grid_id"].isin(attributes["grid_id"])].copy()
    if len(final) != len(attributes) or final["grid_id"].duplicated().any():
        raise ValueError("raw SGIS geometry does not match final grid IDs")
    return final.sort_values("grid_id").reset_index(drop=True)


def map_sgis_to_ngii(sgis: gpd.GeoDataFrame, ngii: gpd.GeoDataFrame) -> pd.DataFrame:
    """Create deterministic 1:1 mapping only for coincident centroid and polygon grids."""
    if sgis.crs is None or ngii.crs is None:
        raise ValueError("SGIS and NGII CRS are required")
    sgis_data = sgis[["grid_id", "geometry"]].copy().to_crs(ANALYSIS_CRS)
    ngii_data = ngii[[NGII_GRID_ID_COLUMN, "geometry"]].copy().to_crs(ANALYSIS_CRS)
    if sgis_data["grid_id"].duplicated().any() or ngii_data[NGII_GRID_ID_COLUMN].duplicated().any():
        raise ValueError("grid mapping inputs must have unique IDs")
    sgis_points = gpd.GeoDataFrame(sgis_data[["grid_id"]], geometry=sgis_data.geometry.centroid, crs=ANALYSIS_CRS)
    ngii_points = gpd.GeoDataFrame(ngii_data[[NGII_GRID_ID_COLUMN]], geometry=ngii_data.geometry.centroid, crs=ANALYSIS_CRS)
    nearest = gpd.sjoin_nearest(sgis_points, ngii_points, how="left", distance_col="centroid_distance_m")
    if len(nearest) != len(sgis_data) or nearest["grid_id"].duplicated().any() or nearest[NGII_GRID_ID_COLUMN].isna().any() or nearest[NGII_GRID_ID_COLUMN].duplicated().any():
        raise ValueError("SGIS-to-NGII mapping is not one-to-one")
    if not nearest["centroid_distance_m"].eq(0).all():
        raise ValueError("SGIS and NGII grid centroids are not identical")
    mapping = nearest[["grid_id", NGII_GRID_ID_COLUMN]].merge(sgis_data, on="grid_id").merge(ngii_data, on=NGII_GRID_ID_COLUMN, suffixes=("_sgis", "_ngii"))
    if any(not left.equals_exact(right, tolerance=0) for left, right in zip(mapping.geometry_sgis, mapping.geometry_ngii)):
        raise ValueError("SGIS and NGII grid polygons are not identical")
    return mapping[["grid_id", NGII_GRID_ID_COLUMN]].sort_values("grid_id").reset_index(drop=True)


def calculate_elderly_features(mapping: pd.DataFrame, population: gpd.GeoDataFrame, elderly: gpd.GeoDataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    """Join NGII values and calculate ratio without null-to-zero conversion or clamping."""
    if mapping["grid_id"].isna().any() or mapping["grid_id"].duplicated().any() or mapping[NGII_GRID_ID_COLUMN].isna().any() or mapping[NGII_GRID_ID_COLUMN].duplicated().any():
        raise ValueError("grid mapping must be one-to-one")
    pop = population[[NGII_GRID_ID_COLUMN, NGII_VALUE_COLUMN]].rename(columns={NGII_VALUE_COLUMN: "population"})
    old = elderly[[NGII_GRID_ID_COLUMN, NGII_VALUE_COLUMN]].rename(columns={NGII_VALUE_COLUMN: "elderly_population"})
    result = mapping.merge(pop, on=NGII_GRID_ID_COLUMN, how="left", validate="one_to_one").merge(old, on=NGII_GRID_ID_COLUMN, how="left", validate="one_to_one")
    population_values = pd.to_numeric(result["population"], errors="coerce")
    elderly_values = pd.to_numeric(result["elderly_population"], errors="coerce")
    invalid_population_zero_elderly = population_values.eq(0) & elderly_values.gt(0)
    invalid_elderly_over_population = elderly_values.gt(population_values)
    negative_population = population_values.dropna().lt(0)
    negative_elderly = elderly_values.dropna().lt(0)
    if invalid_population_zero_elderly.any() or invalid_elderly_over_population.any() or negative_population.any() or negative_elderly.any():
        raise ValueError("NGII population and elderly values are invalid")
    result["elderly_ratio"] = pd.NA
    valid_ratio = population_values.gt(0) & elderly_values.notna()
    result.loc[valid_ratio, "elderly_ratio"] = elderly_values.loc[valid_ratio] / population_values.loc[valid_ratio]
    result["elderly_ratio"] = pd.to_numeric(result["elderly_ratio"], errors="coerce")
    if not result.loc[result["elderly_ratio"].notna(), "elderly_ratio"].between(0, 1).all():
        raise ValueError("elderly ratio is outside 0..1")
    report = {
        "population_zero_elderly_positive_count": int(invalid_population_zero_elderly.sum()),
        "elderly_over_population_count": int(invalid_elderly_over_population.sum()),
        "negative_population_count": int(negative_population.sum()),
        "negative_elderly_count": int(negative_elderly.sum()),
    }
    result["population_source"] = "NGII"
    result["population_reference_date"] = NGII_REFERENCE_DATE
    result["elderly_population_source"] = "NGII"
    result["elderly_reference_date"] = NGII_REFERENCE_DATE
    return result.drop(columns=NGII_GRID_ID_COLUMN).sort_values("grid_id").reset_index(drop=True), report


def build_elderly_features() -> tuple[pd.DataFrame, dict[str, object]]:
    population_path, elderly_path = find_ngii_archives()
    population, population_report = load_ngii_dataset(population_path)
    elderly, elderly_report = load_ngii_dataset(elderly_path)
    validate_ngii_pair(population, elderly)
    sgis = load_final_sgis_grid_geometries()
    mapping = map_sgis_to_ngii(sgis, population)
    result, validation = calculate_elderly_features(mapping, population, elderly)
    sgis_population = pd.read_csv(GRID_CSV, dtype={"grid_id": "string"})[["grid_id", "population"]]
    comparison = result[["grid_id", "population"]].merge(sgis_population, on="grid_id", suffixes=("_ngii", "_sgis"))
    common = comparison.dropna(subset=["population_ngii", "population_sgis"])
    difference = common["population_ngii"] - common["population_sgis"]
    report = {
        "population_archive": str(population_path), "elderly_archive": str(elderly_path),
        "population_report": population_report, "elderly_report": elderly_report,
        "sgis_grid_count": len(sgis), "mapping_success_count": len(mapping), "mapping_failure_count": len(sgis) - len(mapping),
        "elderly_age_threshold": ELDERLY_AGE_THRESHOLD,
        "elderly_age_definition_status": "ELDERLY_AGE_DEFINITION_NEEDS_SOURCE_CONFIRMATION",
        "sgis_ngii_population_common_count": len(common),
        "ngii_minus_sgis_population_median": None if difference.empty else float(difference.median()),
        "ngii_minus_sgis_population_mean": None if difference.empty else float(difference.mean()),
        **validation,
    }
    return result, report


def write_elderly_features(data: pd.DataFrame, output_dir: Path = PROCESSED_DIR) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    data.to_csv(output_dir / GRID_ELDERLY_CSV.name, index=False, encoding="utf-8")


def main() -> None:
    data, report = build_elderly_features()
    write_elderly_features(data)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
