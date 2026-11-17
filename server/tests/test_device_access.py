"""인증 요청과 기기별 통화 소유권 경계를 외부 API 없이 확인한다."""

import tempfile
import unittest
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from server.main import app
from server.security import access
from server.security.device_store import DeviceStore
from server.security.limits import WindowLimiter
from tests.api_helpers import StubRiskAnalyzer, utterance


class DeviceAccessTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.store = DeviceStore(Path(directory.name) / "devices.json")
        patcher = patch.object(access, "device_store", self.store)
        patcher.start()
        self.addCleanup(patcher.stop)
        state_patcher = patch.object(app.state, "warning_manager", None, create=True)
        state_patcher.start()
        self.addCleanup(state_patcher.stop)
        analyzer_patcher = patch.object(app.state, "risk_analyzer", StubRiskAnalyzer(), create=True)
        analyzer_patcher.start()
        self.addCleanup(analyzer_patcher.stop)
        self.token = self.store.issue_device()
        self.other_token = self.store.issue_device()
        self.owner = self.store.authenticate(self.token)
        self.store.register_conversation(self.owner, "owned-call")
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def test_only_owner_can_invoke_conversation_operations(self):
        endpoints = [
            ("get", "/api/v1/utterances/results?conversation_id=owned-call", None),
            ("get", "/api/v1/notifications?conversation_id=owned-call", None),
            ("post", "/api/v1/notifications/ack", {"conversation_id": "owned-call", "event_id": "event"}),
            ("post", "/api/v1/conversations/end", {"conversation_id": "owned-call", "last_utterance_id": 1}),
            ("post", "/api/v1/conversations/withdraw", {"conversation_id": "owned-call"}),
        ]
        for method, path, body in endpoints:
            with self.subTest(path=path):
                def send(token=None):
                    headers = {"Authorization": f"Bearer {token}"} if token else {}
                    return self.client.request(method, path, headers=headers, json=body)
                self.assertEqual(401, send().status_code)
                self.assertEqual(401, send("invalid").status_code)
                self.assertEqual(404, send(self.other_token).status_code)
                # 소유자 요청은 인증 경계를 통과해 데이터 없음 등의 서비스 응답에 도달한다.
                self.assertNotIn(send(self.token).status_code, (401, 403))

    def test_device_registration_issues_usable_token_and_limits_requests(self):
        with patch("server.security.limits.device_registrations", WindowLimiter(1, 60)), \
             patch("server.security.limits.total_device_registrations", WindowLimiter(10, 60)):
            response = self.client.post("/api/v1/devices/register")
            self.assertEqual(201, response.status_code)
            self.assertEqual("no-store", response.headers["cache-control"])
            self.assertIsNotNone(self.store.authenticate(response.json()["token"]))
            self.assertEqual(429, self.client.post("/api/v1/devices/register").status_code)

    def test_analysis_and_retry_reject_other_devices(self):
        calls = [
            ("/api/v1/utterances/analyze", utterance(conversation_id="owned-call") | {"masking_status": "succeeded"}),
            ("/api/v1/utterances/analyze/retry", {"conversation_id": "owned-call", "utterance_id": 1}),
        ]
        for path, body in calls:
            with self.subTest(path=path), patch("server.analysis.router.run_analysis") as run:
                self.assertEqual(401, self.client.post(path, json=body).status_code)
                self.assertEqual(404, self.client.post(path, json=body, headers={"Authorization": f"Bearer {self.other_token}"}).status_code)
                run.assert_not_called()

    def test_stt_requires_token_and_binds_new_conversation(self):
        with self.assertRaises(WebSocketDisconnect):
            with self.client.websocket_connect("/api/v1/stt"):
                pass

        @asynccontextmanager
        async def fake_connection(_settings):
            yield object()

        with patch("server.stt.router.load_stt_settings", return_value=object()), \
             patch("server.stt.router.open_stt_connection", fake_connection), \
             patch("server.stt.router.relay_audio", new_callable=AsyncMock):
            with self.client.websocket_connect(
                "/api/v1/stt", headers={"Authorization": f"Bearer {self.token}"}
            ) as ws:
                ws.send_json({"type": "start", "consent": True, "audio_format": "pcm_s16le", "sample_rate": 16000, "channels": 1})
                ready = ws.receive_json()
                self.assertEqual("ready", ready["type"])
                self.store.require_owner(self.owner, ready["conversation_id"])
                with self.assertRaises(PermissionError):
                    self.store.require_owner(self.store.authenticate(self.other_token), ready["conversation_id"])


if __name__ == "__main__":
    unittest.main()
