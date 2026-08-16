"""Tests for explicit task 1 and task 2 file loading."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from risk_speech_ai.loader import InputDataError, load_stt_text, load_tuned_result


def valid_payload() -> dict[str, object]:
    return {
        "utterance_id": 4,
        "tuned_text": "보정 문장",
        "is_tuned": True,
        "has_unclear": False,
        "unclear_segments": [],
    }


class LoaderTests(unittest.TestCase):
    def test_removes_only_terminal_cr_lf_from_raw_text(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "result0004.txt"
            path.write_text("  서울 중앙 지검입니다 \r\n", encoding="utf-8")

            self.assertEqual("  서울 중앙 지검입니다 ", load_stt_text(path))

    def test_loads_valid_json_from_explicit_path_regardless_of_extension(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tuned_result0004.txt"
            path.write_text(json.dumps(valid_payload()), encoding="utf-8")

            self.assertEqual(valid_payload(), load_tuned_result(path))

    def test_reports_missing_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            missing_path = Path(directory) / "missing.txt"

            with self.assertRaises(FileNotFoundError):
                load_stt_text(missing_path)
            with self.assertRaises(FileNotFoundError):
                load_tuned_result(missing_path)

    def test_reports_malformed_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "broken.json"
            path.write_text("{not valid json", encoding="utf-8")

            with self.assertRaises(InputDataError):
                load_tuned_result(path)

    def test_reports_missing_required_json_field(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "missing-field.json"
            payload = valid_payload()
            del payload["has_unclear"]
            path.write_text(json.dumps(payload), encoding="utf-8")

            with self.assertRaises(InputDataError):
                load_tuned_result(path)
