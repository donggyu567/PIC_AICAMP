"""Run the existing AI pipeline with integrated GIS features and AWS 915 context."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import pandas as pd

from ai.analyzer import analyze_grids
from ai.coverage import calculate_coverage_comparison
from ai.recommendation import recommend_shelters
from .build_ai_input import OUTPUT_PATH as INTEGRATION_GRID_PATH


ROOT = Path(__file__).resolve().parents[1]
WEATHER_PATH = ROOT / "data" / "raw" / "weather" / "kma_aws_hourly_915_samga_cleaned.csv"
CANDIDATES_PATH = ROOT / "data" / "processed" / "gis" / "hapcheon_mobile_shelter_candidate_coverage.json"
ANALYSIS_DIR = ROOT / "data" / "processed" / "analysis"


def select_latest_valid_weather(weather: pd.DataFrame) -> dict[str, Any]:
    """Select the latest timestamp with numeric temperature and valid humidity."""
    required = {"station_id", "station_name", "observed_at", "temperature", "humidity"}
    if not required.issubset(weather.columns):
        raise ValueError("weather input is missing required fields")
    data = weather.copy()
    data["observed_at"] = pd.to_datetime(data["observed_at"], errors="coerce")
    data["temperature"] = pd.to_numeric(data["temperature"], errors="coerce")
    data["humidity"] = pd.to_numeric(data["humidity"], errors="coerce")
    valid = data["observed_at"].notna() & data["temperature"].notna() & data["humidity"].between(0, 100)
    if not valid.any():
        raise ValueError("weather input has no valid observation")
    latest = data.loc[valid].sort_values("observed_at", kind="mergesort").iloc[-1]
    return {
        "analysis_reference_time": latest["observed_at"].isoformat(sep=" "),
        "station_id": str(latest["station_id"]), "station_name": latest["station_name"],
        "temperature": float(latest["temperature"]), "humidity": float(latest["humidity"]),
    }


def _nullable(value: Any) -> Any:
    if pd.isna(value):
        return None
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def build_payload(grid_features: pd.DataFrame, weather: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Inject one shared weather context without changing any GIS feature values."""
    required = {"grid_id", "region_code", "region_name", "population", "elderly_population", "elderly_ratio", "farmland_ratio", "nearest_shelter_distance_m", "current_covered", "grid_area_m2"}
    if not required.issubset(grid_features.columns) or grid_features["grid_id"].isna().any() or grid_features["grid_id"].duplicated().any():
        raise ValueError("integration grid features are invalid")
    payload: list[dict[str, Any]] = []
    for row in grid_features.to_dict("records"):
        payload.append({
            "grid_id": row["grid_id"], "region_code": _nullable(row["region_code"]), "region_name": _nullable(row["region_name"]),
            "population": _nullable(row["population"]), "elderly_population": _nullable(row["elderly_population"]),
            "elderly_ratio": _nullable(row["elderly_ratio"]), "farmland_ratio": _nullable(row["farmland_ratio"]),
            "nearest_shelter_distance_m": _nullable(row["nearest_shelter_distance_m"]), "current_covered": _nullable(row["current_covered"]),
            "grid_area_m2": _nullable(row["grid_area_m2"]), "temperature": weather["temperature"], "humidity": weather["humidity"],
        })
    return payload


def run_pipeline(
    grid_features: pd.DataFrame, weather: pd.DataFrame, candidates: Sequence[Mapping[str, Any]], n_shelters: int
) -> dict[str, Any]:
    context = select_latest_valid_weather(weather)
    payload = build_payload(grid_features, context)
    analyzed = analyze_grids(payload)
    by_id = {result["grid_id"]: result for result in analyzed}
    analysis_grids = [{**grid, **by_id[grid["grid_id"]]} for grid in payload]
    recommendations = recommend_shelters(analysis_grids, candidates, n_shelters)
    coverage = calculate_coverage_comparison(analysis_grids, recommendations)
    return {"context": context, "payload": payload, "analysis": analyzed, "analysis_grids": analysis_grids, "recommendations": recommendations, "coverage": coverage}


def _analysis_frame(analysis_grids: Sequence[Mapping[str, Any]]) -> pd.DataFrame:
    fields = ["grid_id", "analysis_status", "missing_fields", "heat_score", "elderly_score", "farmland_score", "coverage_gap_score", "vulnerability_score", "risk_level", "installation_need_score", "installation_rank", "blind_spot", "main_factors"]
    frame = pd.DataFrame(analysis_grids)[fields]
    for field in ("missing_fields", "main_factors"):
        frame[field] = frame[field].map(lambda value: json.dumps(value, ensure_ascii=False, separators=(",", ":")))
    return frame


def write_outputs(run: Mapping[str, Any], n_shelters: int, output_dir: Path = ANALYSIS_DIR) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "analysis": output_dir / "hapcheon_ai_analysis.csv",
        "recommendations": output_dir / f"hapcheon_ai_recommendations_n{n_shelters}.json",
        "coverage": output_dir / f"hapcheon_ai_before_after_n{n_shelters}.json",
        "metadata": output_dir / "hapcheon_ai_run_metadata.json",
    }
    _analysis_frame(run["analysis_grids"]).to_csv(paths["analysis"], index=False, encoding="utf-8")
    paths["recommendations"].write_text(json.dumps(run["recommendations"], ensure_ascii=False, indent=2), encoding="utf-8")
    paths["coverage"].write_text(json.dumps(run["coverage"], ensure_ascii=False, indent=2), encoding="utf-8")
    paths["metadata"].write_text(json.dumps({**run["context"], "requested_n": n_shelters}, ensure_ascii=False, indent=2), encoding="utf-8")
    return paths


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-shelters", type=int, default=5)
    args = parser.parse_args()
    grid_features = pd.read_csv(INTEGRATION_GRID_PATH, dtype={"grid_id": "string"})
    weather = pd.read_csv(WEATHER_PATH)
    candidates = json.loads(CANDIDATES_PATH.read_text(encoding="utf-8"))
    run = run_pipeline(grid_features, weather, candidates, args.n_shelters)
    paths = write_outputs(run, args.n_shelters)
    print(json.dumps({"context": run["context"], "recommendation_count": len(run["recommendations"]), "coverage": run["coverage"], "outputs": {key: str(path) for key, path in paths.items()}}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
