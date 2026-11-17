import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from backend.schemas import ModelResultRequest
from backend.services import analysis_service
from backend.stores.analysis_file_store import AnalysisFileStore
from server.main import app
from server.security.access import authenticated_device
from tests.api_helpers import payload


class SummaryApiTests(unittest.TestCase):
    def setUp(self):
        folder = self.enterContext(tempfile.TemporaryDirectory())
        self.store = AnalysisFileStore(Path(folder))
        self.enterContext(patch.object(analysis_service, "analysis_store", self.store))
        self.enterContext(patch("server.analysis.lifecycle_router.require_conversation_owner"))
        self.enterContext(patch("server.analysis.lifecycle_router.limits.analysis_requests.allow", return_value=True))
        self.enterContext(patch.dict("os.environ", {"PIC_CONTEXT_MODEL": "", "PIC_AI_MODE": "disabled"}))
        app.dependency_overrides[authenticated_device] = lambda: "device"
        self.addCleanup(app.dependency_overrides.pop, authenticated_device, None)
        self.client = self.enterContext(TestClient(app))
        self.enterContext(patch.dict("os.environ", {"PIC_CONTEXT_MODEL": "test-model"}))
        analysis_service.process_model_result(
            ModelResultRequest(**payload(conversation_id="call", score=0.9)), app.state.warning_manager,
        )
        self.summary = {
            "title": "통화 요약",
            "summary": "송금 요구",
            "key_utterances": [{"utterance_id": 1, "reason": "이체 요구"}],
            "advice": "직접 확인하세요.",
        }
        self.create = Mock(return_value=self.completed(self.summary))
        app.state.llm_client = SimpleNamespace(responses=SimpleNamespace(create=self.create))

    def completed(self, summary):
        return SimpleNamespace(status="completed", output=[], output_text=json.dumps(summary, ensure_ascii=False))

    def post(self, endpoint, **fields):
        return self.client.post(f"/api/v1/conversations/{endpoint}", json={"conversation_id": "call", **fields})

    def test_summary_is_stored_and_reused_in_summary_and_end_responses(self):
        self.assertEqual(self.post("summary").status_code, 409)
        ended = self.post("end", last_utterance_id=1)
        self.assertEqual(ended.status_code, 200, ended.text)
        self.assertIsNone(ended.json()["title"])
        self.assertIsNone(ended.json()["summary"])
        self.create.assert_not_called()

        invalid = self.summary | {"key_utterances": [{"utterance_id": 99, "reason": "없는 발화"}]}
        self.create.side_effect = [self.completed(invalid), self.completed(self.summary), self.completed(self.summary)]
        self.assertEqual(self.post("summary").status_code, 503)
        with patch("backend.stores.analysis_file_store.os.replace", side_effect=OSError("disk")):
            self.assertEqual(self.post("summary").status_code, 503)
        self.assertIsNone(self.store.load("call").summary)
        response = self.post("summary")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json(), self.summary)
        self.assertEqual(self.store.load("call").summary.model_dump(), self.summary)

        app.state.llm_client = None
        self.assertEqual(self.post("summary").json(), self.summary)
        self.assertEqual(self.post("end", last_utterance_id=1).json(), ended.json() | {
            "title": self.summary["title"],
            "summary": self.summary["summary"],
        })
        self.assertEqual(self.create.call_count, 3)
        self.assertEqual(self.post("withdraw").status_code, 200)
        self.assertFalse(self.store.path_for("call").exists())
        self.assertEqual(self.post("summary").status_code, 409)

    def test_withdraw_discards_summary_from_in_progress_request(self):
        self.assertEqual(self.post("end", last_utterance_id=1).status_code, 200)
        generating, release = Event(), Event()

        def delayed_summary(**kwargs):
            generating.set()
            if not release.wait(5):
                raise TimeoutError("test did not release summary")
            return self.completed(self.summary)

        self.create.side_effect = delayed_summary
        with ThreadPoolExecutor(max_workers=2) as pool:
            pending = pool.submit(self.post, "summary")
            try:
                self.assertTrue(generating.wait(5))
                ended = pool.submit(self.post, "end", last_utterance_id=1).result(timeout=3)
                self.assertEqual(ended.status_code, 200, ended.text)
                self.assertIsNone(ended.json()["summary"])
                withdrawn = pool.submit(self.post, "withdraw").result(timeout=3)
                self.assertEqual(withdrawn.status_code, 200, withdrawn.text)
            finally:
                release.set()
            self.assertEqual(pending.result(timeout=5).status_code, 409)
        self.assertFalse(self.store.path_for("call").exists())
