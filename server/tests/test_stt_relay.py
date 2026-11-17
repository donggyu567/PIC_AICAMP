import asyncio
import base64
import json
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from server.main import app


START = {
    "type": "start", "consent": True, "audio_format": "pcm_s16le",
    "sample_rate": 16000, "channels": 1,
}


class FakeProvider:
    """네트워크만 대체하고 실제 공급자 메시지 변환·라우터를 통과시킨다."""

    def __init__(self, mode="normal"):
        self.events = asyncio.Queue()
        self.events.put_nowait(json.dumps({"message_type": "session_started"}))
        self.sent = []
        self.closed = False
        self.mode = mode

    async def recv(self):
        return await self.events.get()

    async def send(self, payload):
        data = json.loads(payload)
        self.sent.append(data)
        if data["commit"]:
            if self.mode == "timeout":
                return
            event = {"message_type": "committed_transcript", "text": "같은 문장"}
            if self.mode == "error":
                event = {"message_type": "quota_exceeded", "error": "SECRET RAW CONTENT"}
        else:
            event = {"message_type": "partial_transcript", "text": "RAW PARTIAL"}
        await self.events.put(json.dumps(event))

    async def close(self):
        self.closed = True


class SttRelayTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch("server.security.access.authenticate_header", return_value="test-device"))
        self.enterContext(patch("server.security.access.device_store"))
        self.provider = FakeProvider()
        self.env = patch.dict("os.environ", {"ELEVENLABS_API_KEY": "test-key"})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.connect_patch = patch(
            "server.stt.elevenlabs.connect", new_callable=AsyncMock, return_value=self.provider,
        )
        self.connect = self.connect_patch.start()
        self.addCleanup(self.connect_patch.stop)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def receive_until_terminal(self, ws):
        messages = []
        for _ in range(30):
            message = ws.receive_json()
            messages.append(message)
            if message["type"] in ("error", "stopped"):
                return messages
        self.fail("terminal message missing")

    def test_stream_commits_and_final_flush_preserve_repeated_utterances(self):
        with self.client.websocket_connect("/api/v1/stt") as ws:
            ws.send_json(START)
            ready = ws.receive_json()
            self.assertEqual(ready["type"], "ready")
            for _ in range(6):
                ws.send_bytes(bytes(32000))
            ws.send_json({"type": "stop"})
            messages = self.receive_until_terminal(ws)
            final = [m for m in messages if m["type"] == "transcript"]
            self.assertEqual([m["utterance_id"] for m in final], [1, 2])
            self.assertTrue(all(m["conversation_id"] == ready["conversation_id"] for m in final))
            self.assertNotIn("RAW PARTIAL", json.dumps(messages))
            self.assertEqual(messages[-1]["last_utterance_id"], 2)
            self.assertEqual(messages[-1]["reason"], "user_stop")
            with self.assertRaises(WebSocketDisconnect):
                ws.receive_json()
        self.assertTrue(self.provider.closed)
        self.assertEqual(sum(m["commit"] for m in self.provider.sent), 2)
        self.assertEqual(sum(len(base64.b64decode(m["audio_base_64"])) for m in self.provider.sent), 192000)
        uri = self.connect.call_args.args[0]
        self.assertIn("commit_strategy=manual", uri)
        self.assertNotIn("test-key", uri)
        self.assertEqual(self.connect.call_args.kwargs["additional_headers"], {"xi-api-key": "test-key"})

    def test_no_audio_stops_without_waiting_for_transcript(self):
        with self.client.websocket_connect("/api/v1/stt") as ws:
            ws.send_json(START)
            ws.receive_json()
            ws.send_json({"type": "stop"})
            self.assertEqual(self.receive_until_terminal(ws)[-1]["last_utterance_id"], 0)
        self.assertEqual(self.provider.sent, [])

    def test_start_required_and_missing_key_is_safe(self):
        with self.client.websocket_connect("/api/v1/stt") as ws:
            ws.send_json({"type": "stop"})
            self.assertEqual(ws.receive_json()["code"], "invalid_state")
        with patch.dict("os.environ", {"ELEVENLABS_API_KEY": ""}):
            with self.client.websocket_connect("/api/v1/stt") as ws:
                ws.send_json(START)
                self.assertEqual(ws.receive_json()["code"], "stt_unavailable")
        self.connect.assert_not_called()

    def test_invalid_audio_and_duplicate_start_close_connection(self):
        for payload, expected in ((b"x", "invalid_audio"), (START, "invalid_state")):
            with self.subTest(expected=expected):
                provider = FakeProvider()
                self.connect.return_value = provider
                with self.client.websocket_connect("/api/v1/stt") as ws:
                    ws.send_json(START)
                    ws.receive_json()
                    if isinstance(payload, bytes):
                        ws.send_bytes(payload)
                    else:
                        ws.send_json(payload)
                    self.assertEqual(ws.receive_json()["code"], expected)
                self.assertTrue(provider.closed)

    def test_provider_failure_does_not_leak_raw_error_or_report_success(self):
        self.provider.mode = "error"
        with self.client.websocket_connect("/api/v1/stt") as ws:
            ws.send_json(START)
            ws.receive_json()
            ws.send_bytes(bytes(3200))
            ws.send_json({"type": "stop"})
            messages = self.receive_until_terminal(ws)
            self.assertEqual(messages[-1]["code"], "stt_failed")
            self.assertNotIn("SECRET", json.dumps(messages))
        self.assertTrue(self.provider.closed)

    def test_final_result_timeout_is_error(self):
        self.provider.mode = "timeout"
        with patch("server.stt.router.PROVIDER_TIMEOUT_SECONDS", 0.03):
            with self.client.websocket_connect("/api/v1/stt") as ws:
                ws.send_json(START)
                ws.receive_json()
                ws.send_bytes(bytes(3200))
                ws.send_json({"type": "stop"})
                messages = self.receive_until_terminal(ws)
                self.assertEqual(messages[-1]["code"], "finalization_timeout")

    def test_time_limit_flushes_pending_audio(self):
        with patch("server.stt.router.MAX_SESSION_SECONDS", 1):
            with self.client.websocket_connect("/api/v1/stt") as ws:
                ws.send_json(START)
                ws.receive_json()
                ws.send_bytes(bytes(3200))
                messages = self.receive_until_terminal(ws)
                self.assertEqual(messages[-1]["reason"], "time_limit")
                self.assertEqual(messages[-1]["last_utterance_id"], 1)

    def test_transient_connect_failure_retries_before_audio(self):
        self.connect.side_effect = [OSError("private upstream detail"), self.provider]
        with self.client.websocket_connect("/api/v1/stt") as ws:
            ws.send_json(START)
            self.assertEqual(ws.receive_json()["type"], "ready")
            ws.send_json({"type": "stop"})
            self.receive_until_terminal(ws)
        self.assertEqual(self.connect.await_count, 2)

    def test_disconnect_closes_provider(self):
        with self.client.websocket_connect("/api/v1/stt") as ws:
            ws.send_json(START)
            ws.receive_json()
        self.assertTrue(self.provider.closed)


if __name__ == "__main__":
    unittest.main()
