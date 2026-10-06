"""대체 경고 구현체로 서버 연동만 검증한다. 실제 경고 정책 검증이 아니다."""

import tempfile
import unittest
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import app
from backend.services import analysis_service
from backend.stores.analysis_file_store import AnalysisFileStore
from models.warning_manager.contracts import (
    ConversationWarningState, WarningConfig, WarningEvent, WarningUpdate,
)
from test_analysis_api import payload


def evidence_for(state):
    if state is None or not state.individual_evidence:
        return {"recent": None, "highest": None, "cumulative_events": []}

    def item(utterance):
        return {
            "utterance_id": utterance.utterance_id,
            "text": utterance.tuned_text,
            "risk_score": 100 * utterance.is_phishing_score,
            "risk_types": list(utterance.detected_types),
        }

    return {
        "recent": item(state.individual_evidence[-1]),
        "highest": item(max(state.individual_evidence, key=lambda row: row.is_phishing_score)),
        "cumulative_events": [],
    }


class StubWarningManager:
    """성공 입력에 고정된 경고 시나리오를 반환하는 연동 테스트용 구현체."""

    def __init__(self):
        self.calls = []
        self.fail = False
        self.transform = lambda update: update

    def update_warning(self, model, calculation, previous, config, **flags):
        self.calls.append(deepcopy((model, calculation, previous, config, flags)))
        if self.fail:
            if previous is not None and previous.individual_evidence:
                previous.individual_evidence[0].type_scores["money_transfer"] = 1.0
            raise RuntimeError("private warning failure")
        if model.analysis_status == "error":
            state = previous
            status = previous.status if previous is not None else "none"
            reason = "single_utterance" if previous is not None else None
            notify = None
        else:
            event_id = "event-" + model.conversation_id
            if previous is None:
                events = (WarningEvent(
                    event_id=event_id, initial_calculation=calculation,
                    reason="single_utterance", peak_score=calculation.cumulative_score,
                    last_sequence=model.sequence, utterances=(model,),
                ),)
                evidence = (model,)
            else:
                events = (*previous.events[:-1], replace(
                    previous.events[-1], last_sequence=model.sequence,
                    peak_score=max(previous.events[-1].peak_score, calculation.cumulative_score),
                    utterances=(*previous.events[-1].utterances, model),
                ))
                evidence = (*previous.individual_evidence, model)
            status = "active"
            reason = "single_utterance"
            state = ConversationWarningState(
                conversation_id=model.conversation_id, config=config,
                status=status, cumulative_score=calculation.cumulative_score,
                individual_evidence=evidence, events=events,
            )
            # 같은 ID가 재요청되어도 서버 대기 목록은 한 번만 기록해야 한다.
            notify = event_id
        result = {
            "warning": {"status": status, "reason": reason, "message": "테스트 안내"},
            "evidence": evidence_for(state),
        }
        return self.transform(WarningUpdate(result=result, state=state, notify_event_id=notify))


class WarningAnalysisApiTests(unittest.TestCase):
    path = "/api/v1/dev/model-results"

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.store = AnalysisFileStore(Path(directory.name))
        self.manager = StubWarningManager()
        for patcher in (
            patch.object(analysis_service, "analysis_store", self.store),
            patch.object(app.state, "warning_manager", self.manager, create=True),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def test_disconnected_warning_is_null_not_a_safe_decision(self):
        with patch.object(app.state, "warning_manager", None):
            response = self.client.post(self.path, json=payload())
        self.assertEqual(200, response.status_code)
        self.assertIsNone(response.json()["warning"])
        self.assertIsNone(response.json()["evidence"])
        self.assertEqual([], self.manager.calls)

    def test_state_round_trip_policy_and_notification_dedup(self):
        first = self.client.post(self.path, json=payload(score=0.8))
        self.assertEqual(200, first.status_code)
        self.assertEqual("active", first.json()["warning"]["status"])
        before = self.store.load("api-test")
        restarted = StubWarningManager()
        with (
            patch.object(analysis_service, "analysis_store", AnalysisFileStore(self.store.root)),
            patch.object(app.state, "warning_manager", restarted),
            patch.object(analysis_service, "WarningConfig", return_value=WarningConfig(warning_threshold=90)),
        ):
            second = self.client.post(self.path, json=payload(2, 0.8))
        self.assertEqual(200, second.status_code)
        self.assertEqual(before.warning_state, restarted.calls[0][2])
        self.assertEqual(70.0, restarted.calls[0][3].warning_threshold)
        self.assertEqual(False, restarted.calls[0][4]["is_replay"])
        self.assertEqual(False, restarted.calls[0][4]["conversation_ended"])
        stored = self.store.load("api-test")
        self.assertEqual(["event-api-test"], stored.pending_notification_ids)
        self.assertEqual(2, stored.warning_state.events[-1].last_sequence)
        fetched = self.client.get(self.path, params={"conversation_id": "api-test"})
        self.assertEqual(second.json(), fetched.json())
        self.assertNotIn("warning_state", second.json())
        self.assertNotIn("pending_notification_ids", second.json())

    def test_ai_failure_preserves_warning_state_and_recovery_continues(self):
        first = self.client.post(self.path, json=payload(score=0.8)).json()
        previous = self.store.load("api-test").warning_state
        failed = self.client.post(self.path, json=payload(2, None))
        self.assertEqual(200, failed.status_code)
        self.assertIsNone(failed.json()["current_risk_score"])
        self.assertIsNone(self.manager.calls[-1][1])
        self.assertEqual(previous, self.store.load("api-test").warning_state)
        self.assertEqual(first["evidence"], failed.json()["evidence"])
        recovered = self.client.post(self.path + "/retry", json=payload(2, 0.8))
        self.assertEqual(200, recovered.status_code)
        self.assertEqual(previous, self.manager.calls[-1][2])
        stored = self.store.load("api-test")
        self.assertEqual(1, len(stored.records[-1].previous_attempts))
        self.assertEqual(failed.json(), stored.records[-1].previous_attempts[0].response.model_dump())
        self.assertEqual(["event-api-test"], stored.pending_notification_ids)

    def test_first_ai_failure_keeps_state_none_until_recovered(self):
        failed = self.client.post(self.path, json=payload(1, None))
        self.assertEqual(200, failed.status_code)
        self.assertEqual("none", failed.json()["warning"]["status"])
        self.assertIsNone(self.store.load("api-test").warning_state)
        response = self.client.post(self.path + "/retry", json=payload(score=0.8))
        self.assertEqual(200, response.status_code)
        self.assertIsNotNone(self.store.load("api-test").warning_state)

    def test_warning_exception_cannot_mutate_or_partially_save_previous_state(self):
        self.client.post(self.path, json=payload(score=0.8))
        before = self.store.path_for("api-test").read_text(encoding="utf-8")
        self.manager.fail = True
        with self.assertLogs("backend.services.warning_service", level="WARNING") as logged:
            response = self.client.post(self.path, json=payload(2, 0.8))
        self.assertEqual(503, response.status_code)
        self.assertNotIn("private warning failure", response.text + str(logged.output))
        self.assertEqual(before, self.store.path_for("api-test").read_text(encoding="utf-8"))
        self.manager.fail = False
        self.assertEqual(200, self.client.post(self.path, json=payload(2, 0.8)).status_code)

    def test_invalid_warning_return_is_rejected_before_save(self):
        self.manager.transform = lambda update: replace(
            update, state=replace(update.state, conversation_id="wrong-call"),
        )
        with self.assertLogs("backend.services.warning_service", level="WARNING"):
            response = self.client.post(self.path, json=payload(score=0.8))
        self.assertEqual(503, response.status_code)
        self.assertIsNone(self.store.load("api-test"))

    def test_failure_cannot_erase_previous_warning_state(self):
        self.client.post(self.path, json=payload(score=0.8))
        before = self.store.path_for("api-test").read_text(encoding="utf-8")
        self.manager.transform = lambda update: replace(update, state=None)
        with self.assertLogs("backend.services.warning_service", level="WARNING"):
            response = self.client.post(self.path, json=payload(2, None))
        self.assertEqual(503, response.status_code)
        self.assertEqual(before, self.store.path_for("api-test").read_text(encoding="utf-8"))

    def test_cannot_disconnect_or_silently_enable_warning_mid_conversation(self):
        self.client.post(self.path, json=payload(score=0.8))
        with patch.object(app.state, "warning_manager", None):
            self.assertEqual(503, self.client.post(self.path, json=payload(2)).status_code)
            self.assertEqual(200, self.client.post(self.path, json=payload(conversation_id="plain")).status_code)
        self.assertEqual(409, self.client.post(self.path, json=payload(2, conversation_id="plain")).status_code)
        self.assertEqual(1, len(self.store.get_history("api-test")))
        self.assertEqual(1, len(self.store.get_history("plain")))

    def test_file_failure_does_not_commit_warning_state_or_notification(self):
        with patch("backend.stores.analysis_file_store.os.replace", side_effect=OSError("disk")):
            response = self.client.post(self.path, json=payload(score=0.8))
        self.assertEqual(503, response.status_code)
        self.assertIsNone(self.store.load("api-test"))
        self.assertEqual(200, self.client.post(self.path, json=payload(score=0.8)).status_code)
        self.assertEqual(["event-api-test"], self.store.load("api-test").pending_notification_ids)

    def test_integrated_route_calls_warning_and_checks_disconnect_before_models(self):
        from test_integrated_analysis_api import StubCorrectionClient, StubRiskAnalyzer, utterance
        from models.llm_correction import CorrectionEngine

        provider = StubCorrectionClient()
        analyzer = StubRiskAnalyzer()
        with (
            patch.object(app.state, "risk_analyzer", analyzer, create=True),
            patch("backend.services.pipeline_service.get_correction_engine", return_value=CorrectionEngine(provider)),
        ):
            response = self.client.post("/api/v1/utterances/analyze", json=utterance())
            self.assertEqual(200, response.status_code)
            self.assertIsNotNone(response.json()["warning"])
            with patch.object(app.state, "warning_manager", None):
                blocked = self.client.post("/api/v1/utterances/analyze", json=utterance(2))
            self.assertEqual(503, blocked.status_code)
        self.assertEqual(1, provider.calls)
        self.assertEqual(1, len(analyzer.inputs))


if __name__ == "__main__":
    unittest.main()
