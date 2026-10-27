"""통화 종료를 임시 저장소와 대체 AI로 검증한다. 외부 API는 호출하지 않는다."""

import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.main import app
from backend.services import analysis_service
from backend.stores.analysis_file_store import AnalysisFileStore, ConversationSnapshot
from models.llm_correction import CorrectionEngine
from models.warning_manager.warning_manager import DefaultWarningManager
from tests.api_helpers import (
    StubCorrectionClient, StubRiskAnalyzer, payload, utterance,
)


class ConversationLifecycleTests(unittest.TestCase):
    result_path = "/api/v1/dev/model-results"
    end_path = "/api/v1/conversations/end"

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.store = AnalysisFileStore(Path(directory.name))
        for patcher in (
            patch.object(analysis_service, "analysis_store", self.store),
            patch.object(app.state, "warning_manager", None, create=True),
            patch.object(app.state, "risk_analyzer", None, create=True),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def end(self, conversation_id="api-test"):
        return self.client.post(self.end_path, json={"conversation_id": conversation_id})

    def test_end_persists_utc_timestamp_preserves_results_and_survives_restart(self):
        first = self.client.post(self.result_path, json=payload()).json()
        second = self.client.post(self.result_path, json=payload(2)).json()
        before = self.store.load("api-test").model_dump()
        ended = self.end()
        self.assertEqual(200, ended.status_code)
        self.assertEqual("ended", ended.json()["conversation_status"])
        timestamp = datetime.fromisoformat(ended.json()["ended_at"])
        self.assertEqual(timezone.utc.utcoffset(None), timestamp.utcoffset())
        after = self.store.load("api-test").model_dump()
        for key in before.keys() - {"conversation_status", "ended_at"}:
            self.assertEqual(before[key], after[key])
        with patch.object(analysis_service, "analysis_store", AnalysisFileStore(self.store.root)):
            self.assertEqual(ended.json(), self.end().json())
            self.assertEqual(409, self.client.post(self.result_path, json=payload(3)).status_code)
            for number, expected in ((None, second), (1, first)):
                params = {"conversation_id": "api-test"}
                if number is not None:
                    params["utterance_id"] = number
                fetched = self.client.get(self.result_path, params=params)
                self.assertEqual(200, fetched.status_code)
                self.assertEqual(expected, fetched.json())

    def test_repeated_end_does_not_write_or_change_timestamp(self):
        self.client.post(self.result_path, json=payload())
        first = self.end()
        with patch.object(self.store, "save", side_effect=AssertionError("must not save")):
            second = self.end()
        self.assertEqual(200, second.status_code)
        self.assertEqual(first.json(), second.json())

    def test_missing_and_invalid_requests_do_not_create_files(self):
        self.assertEqual(404, self.end().status_code)
        for body in ({}, {"conversation_id": ""}, {"conversation_id": "   "},
                     {"conversation_id": 12}, {"conversation_id": "x" * 121},
                     {"conversation_id": "x", "ended_at": "client-supplied"}):
            with self.subTest(body=body):
                self.assertEqual(422, self.client.post(self.end_path, json=body).status_code)
        self.assertEqual([], list(self.store.root.iterdir()))

    def test_storage_failure_keeps_call_active_and_end_can_be_retried(self):
        self.client.post(self.result_path, json=payload())
        path = self.store.path_for("api-test")
        before = path.read_text(encoding="utf-8")
        with patch("backend.stores.analysis_file_store.os.replace", side_effect=OSError("disk")):
            self.assertEqual(503, self.end().status_code)
        self.assertEqual(before, path.read_text(encoding="utf-8"))
        self.assertEqual("active", self.store.load("api-test").conversation_status)
        self.assertEqual([], list(self.store.root.glob(".analysis-*.tmp")))
        self.assertEqual(200, self.end().status_code)

    def test_corrupt_file_is_not_overwritten(self):
        path = self.store.path_for("api-test")
        path.write_text("broken-json", encoding="utf-8")
        self.assertEqual(503, self.end().status_code)
        provider = StubCorrectionClient()
        analyzer = StubRiskAnalyzer()
        with (
            patch.object(app.state, "risk_analyzer", analyzer),
            patch("backend.services.pipeline_service.get_correction_engine",
                  return_value=CorrectionEngine(provider)) as correction_factory,
        ):
            self.assertEqual(503, self.client.post(
                "/api/v1/utterances/analyze", json=utterance(1, "api-test"),
            ).status_code)
            correction_factory.assert_not_called()
        self.assertEqual(0, provider.calls)
        self.assertEqual([], analyzer.inputs)
        self.assertEqual("broken-json", path.read_text(encoding="utf-8"))

    def test_failed_tail_can_end_but_cannot_retry_or_append(self):
        self.client.post(self.result_path, json=payload())
        failed = self.client.post(self.result_path, json=payload(2, None)).json()
        self.assertEqual(200, self.end().status_code)
        before = self.store.path_for("api-test").read_text(encoding="utf-8")
        self.assertEqual(409, self.client.post(self.result_path + "/retry", json=payload(2)).status_code)
        self.assertEqual(409, self.client.post(self.result_path, json=payload(3)).status_code)
        fetched = self.client.get(self.result_path, params={"conversation_id": "api-test"})
        self.assertEqual(failed, fetched.json())
        self.assertIsNone(fetched.json()["cumulative_risk_score"])
        self.assertEqual(before, self.store.path_for("api-test").read_text(encoding="utf-8"))

    def test_closed_integrated_requests_do_not_call_correction_or_ai(self):
        provider = StubCorrectionClient()
        analyzer = StubRiskAnalyzer()
        self.client.post(self.result_path, json=payload(score=None))
        self.end()
        with (
            patch.object(app.state, "risk_analyzer", analyzer),
            patch("backend.services.pipeline_service.get_correction_engine",
                  return_value=CorrectionEngine(provider)) as correction_factory,
        ):
            self.assertEqual(409, self.client.post(
                "/api/v1/utterances/analyze", json=utterance(2, "api-test"),
            ).status_code)
            self.assertEqual(409, self.client.post(
                "/api/v1/utterances/analyze/retry",
                json={"conversation_id": "api-test", "utterance_id": 1},
            ).status_code)
            correction_factory.assert_not_called()
        self.assertEqual(0, provider.calls)
        self.assertEqual([], analyzer.inputs)

    def test_end_does_not_affect_other_conversations(self):
        self.client.post(self.result_path, json=payload())
        self.client.post(self.result_path, json=payload(conversation_id="other"))
        self.end()
        self.assertEqual(200, self.client.post(
            self.result_path, json=payload(2, conversation_id="other"),
        ).status_code)
        self.assertEqual("active", self.store.load("other").conversation_status)

    def test_warning_enabled_call_requires_manager_to_finish_without_partial_save(self):
        manager = DefaultWarningManager()
        with patch.object(app.state, "warning_manager", manager):
            response = self.client.post(self.result_path, json=payload(score=0.8))
            self.assertEqual(200, response.status_code, response.text)
        path = self.store.path_for("api-test")
        before = path.read_text(encoding="utf-8")
        self.assertEqual(503, self.end().status_code)
        self.assertEqual(before, path.read_text(encoding="utf-8"))
        with patch.object(app.state, "warning_manager", manager):
            self.assertEqual(200, self.end().status_code)

    def test_end_closes_real_warning_preserves_evidence_and_historical_responses(self):
        manager = DefaultWarningManager()
        with patch.object(app.state, "warning_manager", manager):
            first = self.client.post(self.result_path, json=payload(score=0.55)).json()
            latest = self.client.post(self.result_path, json=payload(2, 0.55)).json()
            before = self.store.load("api-test")
            self.assertEqual("active", before.warning_state.status)
            with (
                patch("backend.services.pipeline_service.get_correction_engine",
                      side_effect=AssertionError("end must not call LLM")),
                patch.object(app.state, "risk_analyzer", StubRiskAnalyzer()),
            ):
                ended = self.end()
                self.assertEqual([], app.state.risk_analyzer.inputs)
        self.assertEqual(200, ended.status_code, ended.text)
        self.assertEqual("previous_warning", ended.json()["warning"]["status"])
        self.assertEqual(latest["evidence"], ended.json()["evidence"])
        after = self.store.load("api-test")
        self.assertEqual("previous_warning", after.warning_state.status)
        self.assertEqual(2, after.warning_state.events[-1].closed_sequence)
        self.assertEqual(before.warning_state.cumulative_score, after.warning_state.cumulative_score)
        self.assertEqual(before.warning_state.individual_evidence, after.warning_state.individual_evidence)
        self.assertEqual(before.warning_state.events[-1].peak_score, after.warning_state.events[-1].peak_score)
        self.assertEqual(before.records, after.records)
        self.assertEqual(before.warning_config, after.warning_config)
        self.assertEqual(ended.json()["warning"], after.final_warning_result["warning"])
        for number, expected in ((1, first), (2, latest)):
            fetched = self.client.get(self.result_path, params={
                "conversation_id": "api-test", "utterance_id": number,
            })
            self.assertEqual(expected, fetched.json())
        # 이미 종료된 통화는 경고 모듈 없이도 저장된 최종 결과를 반환한다.
        with patch.object(self.store, "save", side_effect=AssertionError("repeat must not save")):
            self.assertEqual(ended.json(), self.end().json())

    def test_last_failed_analysis_can_close_previous_warning_without_losing_failure(self):
        with patch.object(app.state, "warning_manager", DefaultWarningManager()):
            self.client.post(self.result_path, json=payload(score=0.8))
            failure = self.client.post(self.result_path, json=payload(2, None)).json()
            before = self.store.load("api-test")
            ended = self.end()
        self.assertEqual(200, ended.status_code, ended.text)
        after = self.store.load("api-test")
        self.assertEqual("previous_warning", after.warning_state.status)
        self.assertEqual(2, after.warning_state.events[-1].closed_sequence)
        self.assertEqual(before.warning_state.cumulative_score, after.warning_state.cumulative_score)
        self.assertEqual(before.records, after.records)
        self.assertEqual(failure["evidence"], ended.json()["evidence"])
        fetched = self.client.get(self.result_path, params={"conversation_id": "api-test"})
        self.assertEqual(failure, fetched.json())

    def test_call_with_only_failed_analysis_ends_without_inventing_warning_state(self):
        with patch.object(app.state, "warning_manager", DefaultWarningManager()):
            self.client.post(self.result_path, json=payload(score=None))
            before = self.store.load("api-test")
            ended = self.end()
        self.assertEqual(200, ended.status_code, ended.text)
        self.assertEqual("none", ended.json()["warning"]["status"])
        self.assertIsNone(ended.json()["warning"]["reason"])
        self.assertTrue(ended.json()["warning"]["message"].strip())
        after = self.store.load("api-test")
        self.assertIsNone(after.warning_state)
        self.assertEqual([], after.notifications)
        self.assertEqual(before.records, after.records)

    def test_safe_call_ends_with_no_warning_event(self):
        with patch.object(app.state, "warning_manager", DefaultWarningManager()):
            self.client.post(self.result_path, json=payload(score=0.1))
            ended = self.end()
        self.assertEqual(200, ended.status_code, ended.text)
        self.assertEqual("none", ended.json()["warning"]["status"])
        self.assertEqual((), self.store.load("api-test").warning_state.events)

    def test_warning_failure_and_storage_failure_leave_all_end_state_unchanged(self):
        manager = DefaultWarningManager()
        with patch.object(app.state, "warning_manager", manager):
            self.client.post(self.result_path, json=payload(score=0.8))
            path = self.store.path_for("api-test")
            before = path.read_text(encoding="utf-8")
            with patch.object(manager, "update_warning", side_effect=RuntimeError("private failure")):
                response = self.end()
            self.assertEqual(503, response.status_code, response.text)
            self.assertNotIn("private failure", response.text)
            self.assertEqual(before, path.read_text(encoding="utf-8"))
            with patch("backend.stores.analysis_file_store.os.replace", side_effect=OSError("disk")):
                self.assertEqual(503, self.end().status_code)
            self.assertEqual(before, path.read_text(encoding="utf-8"))
            self.assertEqual("pending", self.store.load("api-test").notifications[0].status)
            self.assertEqual(200, self.end().status_code)

    def test_legacy_ended_warning_is_finalized_once_without_changing_timestamp(self):
        manager = DefaultWarningManager()
        with patch.object(app.state, "warning_manager", manager):
            original = self.client.post(self.result_path, json=payload(score=0.8)).json()
            path = self.store.path_for("api-test")
            legacy = json.loads(path.read_text(encoding="utf-8"))
            ended_at = datetime.now(timezone.utc)
            legacy["conversation_status"] = "ended"
            legacy["ended_at"] = ended_at.isoformat()
            legacy.pop("final_warning_result", None)
            legacy.pop("notifications")
            path.write_text(json.dumps(legacy), encoding="utf-8")
            with patch.object(manager, "update_warning", wraps=manager.update_warning) as warning_call:
                ended = self.end()
                self.assertEqual(200, ended.status_code, ended.text)
                self.assertEqual(1, warning_call.call_count)
                self.assertTrue(warning_call.call_args.kwargs["conversation_ended"])
                repeated = self.end()
                self.assertEqual(1, warning_call.call_count)
        self.assertEqual(ended.json(), repeated.json())
        self.assertEqual(ended_at, datetime.fromisoformat(ended.json()["ended_at"]))
        snapshot = self.store.load("api-test")
        self.assertEqual(1, snapshot.warning_state.events[-1].closed_sequence)
        self.assertEqual("expired", snapshot.notifications[0].status)
        fetched = self.client.get(self.result_path, params={"conversation_id": "api-test"})
        self.assertEqual(original, fetched.json())

    def test_legacy_files_default_to_active_and_lifecycle_validation_remains_enabled(self):
        self.client.post(self.result_path, json=payload())
        path = self.store.path_for("api-test")
        data = json.loads(path.read_text(encoding="utf-8"))
        data.pop("conversation_status")
        data.pop("ended_at")
        path.write_text(json.dumps(data), encoding="utf-8")
        self.assertEqual("active", self.store.load("api-test").conversation_status)
        for changes in (
            {"conversation_status": "ended"},
            {"ended_at": datetime.now(timezone.utc).isoformat()},
            {"conversation_status": "ended", "ended_at": "2026-01-01T00:00:00"},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                ConversationSnapshot.model_validate_json(json.dumps({**data, **changes}))
        self.assertEqual(200, self.end().status_code)

    def test_concurrent_end_requests_return_same_timestamp(self):
        self.client.post(self.result_path, json=payload())
        with ThreadPoolExecutor(max_workers=4) as pool:
            responses = list(pool.map(lambda _: self.end(), range(4)))
        self.assertEqual([200] * 4, [response.status_code for response in responses])
        self.assertEqual(1, len({response.json()["ended_at"] for response in responses}))

    def test_concurrent_append_and_end_never_reopens_call(self):
        self.client.post(self.result_path, json=payload())
        with ThreadPoolExecutor(max_workers=2) as pool:
            append = pool.submit(self.client.post, self.result_path, json=payload(2))
            ending = pool.submit(self.end)
            status = append.result().status_code
            self.assertEqual(200, ending.result().status_code)
        self.assertIn(status, (200, 409))
        snapshot = self.store.load("api-test")
        self.assertEqual("ended", snapshot.conversation_status)
        self.assertEqual(2 if status == 200 else 1, len(snapshot.records))
        self.assertEqual(409, self.client.post(self.result_path, json=payload(3)).status_code)


if __name__ == "__main__":
    unittest.main()
