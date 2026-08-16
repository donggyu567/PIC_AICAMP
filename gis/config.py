"""File paths and CRS constants for the Hapcheon GIS P0 workflow."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed" / "gis"

BOUNDARY_ZIP = RAW_DIR / "boundary" / "hapcheon_legal_emd_boundary_raw_crs.zip"
POPULATION_CSV = RAW_DIR / "grid" / "sgis_2024_population_500m_cleaned.csv"
GRID_ZIP = RAW_DIR / "grid" / "grid_라마_500M.zip"
CANDIDATES_CSV = RAW_DIR / "candidates" / "hapcheon_candidate_facilities_contract_final_v2.csv"
SHELTERS_CSV = RAW_DIR / "shelters" / "hapcheon_heatwave_shelters_cleaned.csv"
FARMMAP_ZIP = RAW_DIR / "farmmap" / "hapcheon_farmmap_raw_crs.zip"

GRID_CSV = PROCESSED_DIR / "hapcheon_grid_500m.csv"
GRID_GEOJSON = PROCESSED_DIR / "hapcheon_grid_500m.geojson"
CANDIDATE_COVERAGE_CSV = PROCESSED_DIR / "hapcheon_candidate_coverage.csv"
CANDIDATE_COVERAGE_JSON = PROCESSED_DIR / "hapcheon_candidate_coverage.json"
SHELTER_GEOCODING_INPUT_CSV = PROCESSED_DIR / "hapcheon_shelter_geocoding_input.csv"
SHELTER_GEOCODED_CSV = PROCESSED_DIR / "hapcheon_heatwave_shelters_geocoded.csv"
GRID_SHELTER_ACCESSIBILITY_CSV = PROCESSED_DIR / "hapcheon_grid_shelter_accessibility.csv"
GRID_FARMLAND_CSV = PROCESSED_DIR / "hapcheon_grid_farmland.csv"

ANALYSIS_CRS = "EPSG:5179"
API_CRS = "EPSG:4326"
COVERAGE_DISTANCE_M = 300
SHELTER_SERVICE_RADIUS_M = 300
FARMLAND_CODE_COLUMN = "CLSF_CD"
FARMLAND_CODES = {"01", "02", "03", "04"}
NON_FARMLAND_CODES = {"06"}
AREA_TOLERANCE_M2 = 1e-6
