import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.schemas import ModelResultRequest
from backend.services import analysis_service
from backend.stores.analysis_file_store import AnalysisFileStore
from models.llm_correction import CorrectionEngine
from server.main import app
from server.security.access import authenticated_device
from tests.api_helpers import StubCorrectionClient, StubRiskAnalyzer, payload, utterance


class LifecycleApiTests(unittest.TestCase):
    def setUp(self):
        app.dependency_overrides[authenticated_device] = lambda: "test-device"
        self.addCleanup(app.dependency_overrides.pop, authenticated_device, None)
        self.enterContext(patch("server.analysis.router.require_conversation_owner"))
        self.enterContext(patch("server.analysis.lifecycle_router.require_conversation_owner"))
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.store = AnalysisFileStore(Path(directory.name))
        self.enterContext(patch.object(analysis_service, "analysis_store", self.store))
        self.enterContext(patch.dict("os.environ", {"PIC_AI_MODE": "disabled", "PIC_CONTEXT_MODEL": ""}))
        self.client = self.enterContext(TestClient(app))
        self.analyzer = StubRiskAnalyzer()
        app.state.risk_analyzer = self.analyzer
        self.enterContext(patch("backend.services.pipeline_service.get_correction_engine",
                                return_value=CorrectionEngine(StubCorrectionClient())))

    def seed(self, conversation_id="call", score=0.9):
        return analysis_service.process_model_result(
            ModelResultRequest(**payload(conversation_id=conversation_id, score=score)),
            app.state.warning_manager,
        ).model_dump(mode="json")

    def end(self, conversation_id="call", last=1):
        return self.client.post("/api/v1/conversations/end", json={
            "conversation_id": conversation_id, "last_utterance_id": last,
        })

    def test_result_lookup_end_and_repeated_end_preserve_final_analysis(self):
        saved = self.seed()
        for extra in ({}, {"utterance_id": 1}):
            fetched = self.client.get("/api/v1/utterances/results", params={"conversation_id": "call", **extra})
            self.assertEqual(fetched.status_code, 200)
            self.assertEqual(fetched.json(), saved)
            self.assertEqual(fetched.headers["cache-control"], "no-store")
        ended = self.end()
        self.assertEqual(ended.status_code, 200, ended.text)
        self.assertEqual(ended.json()["last_analysis"], saved)
        self.assertEqual(ended.json()["conversation_status"], "ended")
        with patch.object(self.store, "save", side_effect=AssertionError("repeat must not write")):
            self.assertEqual(self.end().json(), ended.json())
        after = self.client.get("/api/v1/utterances/results", params={"conversation_id": "call"})
        self.assertEqual(after.json(), saved)
        new = utterance(number=2, conversation_id="call") | {"masking_status": "succeeded"}
        self.assertEqual(self.client.post("/api/v1/utterances/analyze", json=new).status_code, 409)
        self.assertEqual(self.client.post("/api/v1/utterances/analyze/retry", json={
            "conversation_id": "call", "utterance_id": 1,
        }).status_code, 409)
        self.assertEqual(self.analyzer.inputs, [])

    def test_notifications_acknowledgment_and_expiration(self):
        for conversation_id, acknowledge in (("ack", True), ("expire", False)):
            self.seed(conversation_id)
            params = {"conversation_id": conversation_id}
            listing = self.client.get("/api/v1/notifications", params=params)
            self.assertEqual(listing.status_code, 200, listing.text)
            notification = listing.json()["notifications"][0]
            self.assertEqual(self.client.get("/api/v1/notifications", params=params).json(), listing.json())
            body = params | {"event_id": notification["event_id"]}
            if acknowledge:
                first = self.client.post("/api/v1/notifications/ack", json=body)
                self.assertEqual(first.json()["status"], "acknowledged")
                self.assertEqual(self.client.post("/api/v1/notifications/ack", json=body).json(), first.json())
                self.assertEqual(self.client.get("/api/v1/notifications", params=params).json()["notifications"], [])
            self.assertEqual(self.end(conversation_id).status_code, 200)
            closed = self.client.get("/api/v1/notifications", params=params).json()
            self.assertEqual(closed["conversation_status"], "ended")
            self.assertEqual(closed["notifications"], [])
            late = self.client.post("/api/v1/notifications/ack", json=body)
            self.assertEqual(late.json()["status"], "acknowledged" if acknowledge else "expired")

    def test_missing_result_wrong_last_id_and_storage_failure(self):
        self.assertEqual(self.end().status_code, 404)
        self.assertEqual(self.client.get("/api/v1/utterances/results", params={"conversation_id": "call"}).status_code, 404)
        self.assertEqual(self.client.post("/api/v1/notifications/ack", json={"conversation_id": "call", "event_id": "missing"}).status_code, 404)
        self.assertEqual(self.client.post("/api/v1/conversations/end", json={"conversation_id": "call"}).status_code, 422)
        self.seed(score=None)
        before = self.store.path_for("call").read_bytes()
        self.assertEqual(self.end(last=2).status_code, 409)
        with patch("backend.stores.analysis_file_store.os.replace", side_effect=OSError("disk")):
            self.assertEqual(self.end().status_code, 503)
        self.assertEqual(self.store.path_for("call").read_bytes(), before)
        ended = self.end()
        self.assertEqual(ended.status_code, 200, ended.text)
        self.assertEqual(ended.json()["last_analysis"]["analysis_status"], "error")
        self.assertIsNone(ended.json()["last_analysis"]["cumulative_risk_score"])

    def test_end_waits_for_running_analysis_and_includes_it(self):
        self.seed()
        analyzing, release, ending = Event(), Event(), Event()
        analyze = self.analyzer.analyze
        end_conversation = analysis_service.end_conversation

        def delayed_analysis(model_input):
            analyzing.set()
            if not release.wait(5):
                raise TimeoutError("test did not release analysis")
            return analyze(model_input)

        def tracked_end(*args, **kwargs):
            ending.set()
            return end_conversation(*args, **kwargs)

        with patch.object(self.analyzer, "analyze", side_effect=delayed_analysis), \
                patch.object(analysis_service, "end_conversation", side_effect=tracked_end), \
                ThreadPoolExecutor(max_workers=2) as pool:
            try:
                pending = pool.submit(self.client.post, "/api/v1/utterances/analyze", json=(
                    utterance(number=2, conversation_id="call") | {"masking_status": "succeeded"}
                ))
                self.assertTrue(analyzing.wait(5))
                closing = pool.submit(self.end, last=2)
                self.assertTrue(ending.wait(5))
                self.assertFalse(closing.done())
            finally:
                release.set()
            analyzed, closed = pending.result(timeout=5), closing.result(timeout=5)
        self.assertEqual(analyzed.status_code, 200, analyzed.text)
        self.assertEqual(closed.status_code, 200, closed.text)
        self.assertEqual(closed.json()["last_analysis"], analyzed.json())


if __name__ == "__main__":
    unittest.main()
