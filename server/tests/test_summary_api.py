import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.schemas import ModelResultRequest
from backend.services import analysis_service
from backend.stores.analysis_file_store import AnalysisFileStore
from server.main import app
from server.security.access import authenticated_device
from tests.api_helpers import payload


class SummaryApiTests(unittest.TestCase):
    def test_summary_only_after_end_and_validates_evidence(self):
        with tempfile.TemporaryDirectory() as folder, \
             patch.object(analysis_service, "analysis_store", AnalysisFileStore(Path(folder))), \
             patch("server.analysis.lifecycle_router.require_conversation_owner"), \
             patch.dict("os.environ", {"PIC_CONTEXT_MODEL": "", "PIC_AI_MODE": "disabled"}):
            app.dependency_overrides[authenticated_device] = lambda: "device"
            try:
                with TestClient(app) as client:
                    analysis_service.process_model_result(ModelResultRequest(**payload(conversation_id="call", score=0.9)), app.state.warning_manager)
                    result = SimpleNamespace(status="completed", output=[], output_text=json.dumps({
                        "title": "통화 요약", "summary": "송금 요구", "key_utterances": [{"utterance_id": 1, "reason": "이체 요구"}], "advice": "직접 확인하세요."
                    }, ensure_ascii=False))
                    app.state.llm_client = SimpleNamespace(responses=SimpleNamespace(create=lambda **kwargs: result))
                    self.enterContext(patch.dict("os.environ", {"PIC_CONTEXT_MODEL": "test-model"}))
                    request = {"conversation_id": "call"}
                    self.assertEqual(client.post("/api/v1/conversations/summary", json=request).status_code, 409)
                    self.assertEqual(client.post("/api/v1/conversations/end", json=request | {"last_utterance_id": 1}).status_code, 200)
                    response = client.post("/api/v1/conversations/summary", json=request)
                    self.assertEqual(response.status_code, 200, response.text)
                    self.assertEqual(response.json()["key_utterances"][0]["utterance_id"], 1)
                    result.output_text = result.output_text.replace('"utterance_id": 1', '"utterance_id": 99')
                    self.assertEqual(client.post("/api/v1/conversations/summary", json=request).status_code, 503)
                    self.assertEqual(client.post("/api/v1/conversations/withdraw", json=request).status_code, 200)
                    self.assertEqual(client.post("/api/v1/conversations/summary", json=request).status_code, 409)
                    app.state.llm_client = None
            finally:
                app.dependency_overrides.pop(authenticated_device, None)
