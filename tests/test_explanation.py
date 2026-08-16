from copy import deepcopy
import json
from pathlib import Path

from ai.explanation import build_explanation_input, build_fallback_explanation, format_percentage


def _sources():
    recommendation = {
        "candidate_id": "candidate-1", "recommendation_rank": 2,
        "newly_covered_grid_ids": ["G1", "G2"], "newly_covered_elderly_population": 98,
    }
    candidate = {"candidate_id": "candidate-1", "candidate_name": "유하경로당", "candidate_type": "마을회관및경로당"}
    grids = {
        "G1": {"grid_id": "G1", "region_name": "초계면", "installation_need_score": 68.2, "risk_level": "HIGH", "elderly_ratio": .71, "farmland_ratio": .18, "nearest_shelter_distance_m": 620.3, "main_factors": ["HIGH_ELDERLY_RATIO", "LOW_SHELTER_ACCESSIBILITY"]},
        "G2": {"grid_id": "G2", "region_name": "초계면", "installation_need_score": 61.1, "risk_level": "HIGH", "elderly_ratio": .60, "farmland_ratio": .10, "nearest_shelter_distance_m": 520.0, "main_factors": ["HIGH_HEAT"]},
    }
    coverage = {"before": {"covered_vulnerable_population": 1921, "vulnerable_population_coverage_rate": .195363}, "after": {"covered_vulnerable_population": 2382, "vulnerable_population_coverage_rate": .242245}, "improvement": {"newly_covered_vulnerable_population": 461, "vulnerable_population_coverage_rate_delta": .046883}}
    return recommendation, candidate, grids, coverage


def test_fallback_preserves_identity_rank_and_provided_numbers_without_mutation():
    sources = _sources()
    original = deepcopy(sources)
    payload = build_explanation_input(*sources)
    result = build_fallback_explanation(payload).to_dict()
    assert sources == original
    assert result["candidate_id"] == "candidate-1"
    assert "2순위" in result["summary"]
    assert "98명" in result["expected_effect"]
    assert "19.5%에서 24.2%로 4.7%p" in result["expected_effect"]
    assert "고령인구 비율이 높은 지역" in result["key_reasons"]
    assert "반드시 설치" not in " ".join(str(value) for value in result.values())


def test_optional_grid_fields_are_omitted_not_invented_and_fallback_is_deterministic():
    recommendation, candidate, grids, coverage = _sources()
    grids["G1"] = {"grid_id": "G1", "main_factors": []}
    grids["G2"] = {"grid_id": "G2", "main_factors": []}
    coverage["before"] = {}
    coverage["after"] = {}
    coverage["improvement"] = {}
    payload = build_explanation_input(recommendation, candidate, grids, coverage)
    first = build_fallback_explanation(payload).to_dict()
    assert first == build_fallback_explanation(payload).to_dict()
    assert first["key_reasons"] == ["현재 보호받지 못하는 취약 Grid 2개를 새로 보호할 수 있는 후보"]
    assert "보호율" not in first["expected_effect"]


def test_percentage_display_formatting():
    assert format_percentage(.195363) == "19.5%"
    assert format_percentage(.046883) == "4.7%"
    assert format_percentage(None) is None


def test_real_n5_samples_preserve_existing_recommendation_facts():
    sample_path = Path(__file__).parent / "fixtures" / "llm_explanation_sample_n5.json"
    samples = json.loads(sample_path.read_text(encoding="utf-8"))
    assert [(sample["candidate_name"], sample["recommendation_rank"]) for sample in samples] == [
        ("유하경로당", 1), ("대동경로당", 2), ("교촌경로당", 3)
    ]
    assert [sample["newly_covered_elderly_population"] for sample in samples] == [98, 98, 91]
    assert {factor for sample in samples for grid in sample["covered_grids"] for factor in grid["main_factors"]} == {
        "HIGH_HEAT", "HIGH_ELDERLY_RATIO", "HIGH_FARMLAND_RATIO", "LOW_SHELTER_ACCESSIBILITY"
    }
