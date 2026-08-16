import pandas as pd

from integration.run_real_analysis import build_payload, run_pipeline, select_latest_valid_weather


def _grid_features():
    return pd.DataFrame({
        "grid_id": ["G1", "G2"], "region_code": ["R", "R"], "region_name": ["Region", "Region"],
        "population": [100, None], "elderly_population": [20, None], "elderly_ratio": [0.2, None],
        "farmland_ratio": [0.1, 0.0], "nearest_shelter_distance_m": [400, 0], "current_covered": [False, True], "grid_area_m2": [250000, 250000],
    })


def test_latest_valid_weather_is_deterministic_and_skips_invalid_rows():
    weather = pd.DataFrame({"station_id": [915, 915, 915], "station_name": ["Samga"] * 3, "observed_at": ["2026-08-14 00:00", "2026-08-14 02:00", "2026-08-14 01:00"], "temperature": [30, None, 31], "humidity": [50, 60, 101]})
    selected = select_latest_valid_weather(weather)
    assert selected["analysis_reference_time"] == "2026-08-14 00:00:00" and selected["temperature"] == 30


def test_payload_injects_one_weather_context_and_preserves_elderly_null():
    weather = {"temperature": 30.0, "humidity": 50.0}
    payload = build_payload(_grid_features(), weather)
    assert [row["temperature"] for row in payload] == [30.0, 30.0]
    assert [row["humidity"] for row in payload] == [50.0, 50.0]
    assert payload[1]["elderly_ratio"] is None


def test_pipeline_preserves_rows_statuses_candidates_and_requested_n():
    weather = pd.DataFrame({"station_id": [915], "station_name": ["Samga"], "observed_at": ["2026-08-14 00:00"], "temperature": [30], "humidity": [50]})
    candidates = [{"candidate_id": "C1", "candidate_name": "Candidate", "candidate_type": "A", "covered_grid_ids": ["G1"]}]
    run = run_pipeline(_grid_features(), weather, candidates, 1)
    assert len(run["analysis"]) == 2
    assert {entry["analysis_status"] for entry in run["analysis"]} == {"OK", "INSUFFICIENT_DATA"}
    assert len(run["recommendations"]) <= 1
    assert all(grid_id == "G1" for recommendation in run["recommendations"] for grid_id in recommendation["newly_covered_grid_ids"])
