from copy import deepcopy

import pytest

from ai.alert import evaluate_alerts


def grid(grid_id="G1", **changes):
    value = {
        "grid_id": grid_id, "analysis_status": "OK", "current_covered": False,
        "blind_spot": True, "installation_need_score": 60.0,
        "coverage_gap_score": 50.0, "risk_level": "HIGH",
    }
    value.update(changes)
    return value


def by_id(results, grid_id="G1"):
    return next(result for result in results if result["grid_id"] == grid_id)


def test_initial_priority_blind_spot_is_watch_with_deterministic_reasons():
    result = by_id(evaluate_alerts([grid(installation_need_score=75, coverage_gap_score=75)]))
    assert result["alert_required"] is True and result["alert_level"] == "WATCH"
    assert result["alert_event_types"] == []
    assert result["alert_reason_codes"] == ["HIGH_INSTALLATION_NEED", "TOP_PRIORITY_RANK", "LOW_SHELTER_ACCESSIBILITY", "NEW_BLIND_SPOT"]


def test_initial_top_twenty_percent_uses_batch_rank_and_grid_id_tie_break():
    grids = [grid("G3", installation_need_score=70), grid("G2", installation_need_score=70), grid("G1", installation_need_score=70), grid("G4", installation_need_score=1), grid("G5", installation_need_score=1)]
    results = evaluate_alerts(grids)
    assert by_id(results, "G1")["alert_required"] is True
    assert by_id(results, "G2")["alert_required"] is False
    assert "TOP_PRIORITY_RANK" in by_id(results, "G1")["alert_reason_codes"]


def test_false_blind_spot_is_not_alert_and_insufficient_is_undecidable():
    results = evaluate_alerts([grid("safe", blind_spot=False), grid("missing", analysis_status="INSUFFICIENT_DATA", current_covered=None)])
    assert by_id(results, "safe")["alert_required"] is False
    assert by_id(results, "missing")["alert_required"] is None
    assert by_id(results, "missing")["alert_reason_codes"] == []


@pytest.mark.parametrize("delta, expected", [(9.99, []), (10, ["INSTALLATION_NEED_INCREASED"]), (10.01, ["INSTALLATION_NEED_INCREASED"])])
def test_installation_need_delta_threshold(delta, expected):
    previous = [grid(installation_need_score=60)]
    current = [grid(installation_need_score=60 + delta)]
    result = by_id(evaluate_alerts(current, previous))
    assert result["installation_need_delta"] == pytest.approx(delta)
    assert result["alert_event_types"] == expected
    assert result["alert_required"] is bool(expected)


@pytest.mark.parametrize(
    "previous_level,current_level,expected",
    [("MODERATE", "HIGH", ["RISK_LEVEL_INCREASED"]), ("HIGH", "VERY_HIGH", ["RISK_LEVEL_INCREASED"]), ("HIGH", "HIGH", []), ("HIGH", "MODERATE", [])],
)
def test_risk_level_increase_only(previous_level, current_level, expected):
    result = by_id(evaluate_alerts([grid(risk_level=current_level)], [grid(risk_level=previous_level)]))
    assert result["alert_event_types"] == expected


def test_new_blind_spot_and_warning_started_are_priority_events():
    previous = [grid(blind_spot=False, current_covered=True, installation_need_score=60)]
    current = [grid(installation_need_score=60)]
    result = by_id(evaluate_alerts(current, previous, current_heatwave_warning_active=True, previous_heatwave_warning_active=False))
    assert result["alert_level"] == "URGENT"
    assert result["alert_event_types"] == ["NEW_BLIND_SPOT", "HEATWAVE_WARNING_STARTED"]
    assert "HEATWAVE_WARNING_ACTIVE" in result["alert_reason_codes"]


def test_no_change_does_not_repeat_alert_but_keeps_active_warning_reason():
    current = [grid(installation_need_score=75)]
    result = by_id(evaluate_alerts(current, current, current_heatwave_warning_active=True, previous_heatwave_warning_active=True))
    assert result["alert_required"] is False and result["alert_event_types"] == []
    assert "HEATWAVE_WARNING_ACTIVE" in result["alert_reason_codes"]


def test_matching_is_by_grid_id_and_inputs_are_not_mutated():
    current = [grid("G2", installation_need_score=70), grid("G1", installation_need_score=80)]
    previous = [grid("G1", installation_need_score=60), grid("G2", installation_need_score=70)]
    original = deepcopy((current, previous))
    results = evaluate_alerts(current, previous)
    assert by_id(results, "G1")["alert_event_types"] == ["INSTALLATION_NEED_INCREASED"]
    assert (current, previous) == original and results == evaluate_alerts(current, previous)


def test_duplicate_grid_ids_are_invalid():
    with pytest.raises(ValueError, match="duplicate current"):
        evaluate_alerts([grid("G1"), grid("G1")])
    with pytest.raises(ValueError, match="duplicate previous"):
        evaluate_alerts([grid("G1")], [grid("G1"), grid("G1")])
