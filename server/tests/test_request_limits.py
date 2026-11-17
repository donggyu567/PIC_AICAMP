"""요청 제한과 음성 연결 수 제한의 주요 동작을 확인한다."""

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from server.main import app
from server.security import limits
from server.security.access import authenticated_device
from tests.api_helpers import StubRiskAnalyzer, utterance


class RequestLimitTests(unittest.TestCase):
    def test_window_limit_expires_and_session_slots_are_reused(self):
        limiter = limits.WindowLimiter(limit=2, window_seconds=60)
        with patch("server.security.limits.monotonic", return_value=100):
            self.assertTrue(limiter.allow("device"))
            self.assertTrue(limiter.allow("device"))
            self.assertFalse(limiter.allow("device"))
            self.assertTrue(limiter.blocked("device"))
        with patch("server.security.limits.monotonic", return_value=160):
            self.assertFalse(limiter.blocked("device"))
            self.assertTrue(limiter.allow("device"))

        sessions = limits.SessionLimiter(per_device=1, total=2)
        self.assertTrue(sessions.acquire("a"))
        self.assertFalse(sessions.acquire("a"))
        self.assertTrue(sessions.acquire("b"))
        self.assertFalse(sessions.acquire("c"))
        sessions.release("a")
        self.assertTrue(sessions.acquire("c"))

    def test_analysis_limit_returns_429_before_processing(self):
        app.dependency_overrides[authenticated_device] = lambda: "device"
        self.addCleanup(app.dependency_overrides.pop, authenticated_device, None)
        client = TestClient(app)
        self.addCleanup(client.close)
        with patch.object(limits, "analysis_requests", limits.WindowLimiter(1, 60)), \
             patch("server.analysis.router.require_conversation_owner"), \
             patch.object(app.state, "risk_analyzer", StubRiskAnalyzer(), create=True), \
             patch.object(app.state, "warning_manager", None, create=True), \
             patch.object(app.state, "llm_client", None, create=True):
            body = utterance() | {"masking_status": "succeeded"}
            # 실제 모델은 실행하지 않고 경계에서 제한한다.
            with patch("server.analysis.router.run_analysis", side_effect=RuntimeError("first request reached")):
                with self.assertRaisesRegex(RuntimeError, "first request reached"):
                    client.post("/api/v1/utterances/analyze", json=body)
            response = client.post("/api/v1/utterances/analyze", json=body)
            self.assertEqual(429, response.status_code)
            self.assertEqual("60", response.headers["retry-after"])

    def test_websocket_limit_rejects_before_opening_provider(self):
        limiter = limits.SessionLimiter(per_device=1, total=1)
        self.assertTrue(limiter.acquire("device"))
        client = TestClient(app)
        self.addCleanup(client.close)
        with patch.object(limits, "stt_sessions", limiter), \
             patch("server.security.access.authenticate_header", return_value="device"), \
             patch("server.stt.router.open_stt_connection") as provider:
            with self.assertRaises(WebSocketDisconnect):
                with client.websocket_connect("/api/v1/stt"):
                    pass
            provider.assert_not_called()
        limiter.release("device")

    def test_repeated_invalid_auth_is_temporarily_blocked(self):
        client = TestClient(app)
        self.addCleanup(client.close)
        with patch.object(limits, "invalid_auth_attempts", limits.WindowLimiter(1, 60)), \
             patch("server.security.access.authenticate_header", return_value=None) as authenticate:
            path = "/api/v1/utterances/results?conversation_id=call"
            self.assertEqual(401, client.get(path).status_code)
            self.assertEqual(429, client.get(path).status_code)
            authenticate.assert_called_once()
