import json
import unittest
from unittest.mock import patch

from pydantic import ValidationError

from server.config import MAX_AUDIO_CHUNK_BYTES, load_stt_settings
from server.stt.contracts import (
    StartMessage, StopMessage, StatusMessage, TranscriptMessage,
    parse_client_message, validate_audio_chunk,
)


class SttContractTests(unittest.TestCase):
    def setUp(self):
        self.start = {
            "type": "start", "consent": True, "audio_format": "pcm_s16le",
            "sample_rate": 16000, "channels": 1,
        }

    def test_control_messages(self):
        self.assertIsInstance(parse_client_message(json.dumps(self.start)), StartMessage)
        self.assertIsInstance(parse_client_message('{"type":"stop"}'), StopMessage)

    def test_invalid_start_is_rejected_at_boundary(self):
        for change in (
            {"consent": False}, {"sample_rate": 48000}, {"channels": 2},
            {"audio_format": "wav"}, {"api_key": "must-not-be-sent"},
        ):
            with self.subTest(change=change), self.assertRaises(ValidationError):
                parse_client_message(json.dumps(self.start | change))
        with self.assertRaises(ValidationError):
            parse_client_message("not-json")

    def test_audio_chunk_bounds(self):
        for chunk in (b"\x00\x00", bytes(MAX_AUDIO_CHUNK_BYTES)):
            validate_audio_chunk(chunk)
        for chunk in (b"", b"\x00", bytes(MAX_AUDIO_CHUNK_BYTES + 2)):
            with self.subTest(size=len(chunk)), self.assertRaises(ValueError):
                validate_audio_chunk(chunk)

    def test_status_has_no_transcript_and_final_has_identity(self):
        status = StatusMessage(conversation_id="test-session", status="recognizing")
        self.assertNotIn("text", status.model_dump())
        with self.assertRaises(ValidationError):
            StatusMessage(conversation_id="test-session", status="recognizing", text="raw")
        final = TranscriptMessage(conversation_id="test-session", utterance_id=1, text="안녕하세요")
        self.assertEqual(final.model_dump()["text"], "안녕하세요")
        self.assertNotIn("안녕하세요", repr(final))

    def test_key_is_required_and_hidden_in_settings_repr(self):
        for value in (None, "   "):
            with patch.dict("os.environ", {} if value is None else {"ELEVENLABS_API_KEY": value}, clear=True):
                with self.assertRaisesRegex(RuntimeError, "ELEVENLABS_API_KEY"):
                    load_stt_settings()
        with patch.dict("os.environ", {"ELEVENLABS_API_KEY": " dummy-test-key "}, clear=True):
            settings = load_stt_settings()
            self.assertEqual(settings.api_key, "dummy-test-key")
            self.assertNotIn("dummy-test-key", repr(settings))


if __name__ == "__main__":
    unittest.main()
