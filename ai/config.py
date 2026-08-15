"""Provisional MVP v0.1 analysis settings.

Keep calibration values here so production data can be tuned without changing
the analysis pipeline.
"""

NORMALIZATION_LOWER_PERCENTILE = 5
NORMALIZATION_UPPER_PERCENTILE = 95
MIN_SAMPLES_FOR_ROBUST_SCALING = 20

VULNERABILITY_WEIGHTS = {"heat": 1 / 3, "elderly": 1 / 3, "farmland": 1 / 3}
INSTALLATION_WEIGHTS = {"heat": 0.25, "elderly": 0.25, "farmland": 0.25, "coverage_gap": 0.25}

RISK_THRESHOLDS = {"LOW": 25, "MODERATE": 50, "HIGH": 75}
MAIN_FACTOR_TOP_K = 3
FACTOR_MIN_SCORE = 50

REQUIRED_FEATURES = (
    "heat_exposure_value",
    "elderly_ratio",
    "farmland_ratio",
    "nearest_shelter_distance_m",
)
