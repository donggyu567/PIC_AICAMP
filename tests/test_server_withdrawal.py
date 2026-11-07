"""철회 후 기록 삭제와 진행 중 분석의 늦은 저장 차단을 확인한다."""

import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.schemas import UtteranceRequest
from backend.services import analysis_service, pipeline_service
from backend.stores.analysis_file_store import AnalysisFileStore
from backend.stores.analysis_store import AnalysisConflictError
from models.llm_correction import CorrectionEngine
from server.main import app
from server.security import access
from server.security.device_store import DeviceStore
from tests.api_helpers import StubCorrectionClient, StubRiskAnalyzer, payload, utterance


class WithdrawalTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.store = AnalysisFileStore(Path(self.directory.name))
        self.patcher = patch.object(analysis_service, "analysis_store", self.store)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.devices = DeviceStore(Path(self.directory.name) / "devices.json")
        device_patcher = patch.object(access, "device_store", self.devices)
        device_patcher.start()
        self.addCleanup(device_patcher.stop)

    def test_delete_is_repeatable_and_blocks_recreation_after_restart(self):
        from backend.schemas import ModelResultRequest
        analysis_service.process_model_result(ModelResultRequest.model_validate(payload()))
        token = self.devices.issue_device()
        self.devices.register_conversation(self.devices.authenticate(token), "api-test")
        client = TestClient(app)
        self.addCleanup(client.close)
        for _ in range(2):
            response = client.post("/api/v1/conversations/withdraw", json={"conversation_id": "api-test"}, headers={"Authorization": f"Bearer {token}"})
            self.assertEqual(200, response.status_code)
            self.assertEqual("deleted", response.json()["status"])
        self.assertFalse(self.store.path_for("api-test").exists())
        with patch.object(analysis_service, "analysis_store", AnalysisFileStore(self.store.root)):
            with self.assertRaises(AnalysisConflictError):
                analysis_service.process_model_result(ModelResultRequest.model_validate(payload()))

    def test_withdraw_during_analysis_discards_late_result(self):
        started, release = Event(), Event()

        class WaitingClient(StubCorrectionClient):
            def complete(self, **kwargs):
                started.set()
                if not release.wait(5):
                    raise TimeoutError()
                return super().complete(**kwargs)

        with patch.object(pipeline_service, "get_correction_engine", return_value=CorrectionEngine(WaitingClient())):
            with ThreadPoolExecutor(max_workers=2) as pool:
                pending = pool.submit(pipeline_service.analyze_utterance,
                                      UtteranceRequest.model_validate(utterance()), StubRiskAnalyzer())
                self.assertTrue(started.wait(3))
                deletion = pool.submit(analysis_service.withdraw_conversation, "pipeline-test")
                try:
                    for _ in range(1000):
                        if self.store.withdrawal_path_for("pipeline-test").exists():
                            break
                        Event().wait(0.005)
                    self.assertTrue(self.store.withdrawal_path_for("pipeline-test").exists())
                finally:
                    release.set()
                with self.assertRaises(AnalysisConflictError):
                    pending.result(timeout=5)
                deletion.result(timeout=5)
        self.assertFalse(self.store.path_for("pipeline-test").exists())
