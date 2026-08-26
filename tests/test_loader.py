"""Tests for masked task 1 and tuned task 2 JSON loading."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from risk_speech_ai.loader import (
    InputDataError,
    load_masked_result,
    load_tuned_result,
)


def masked_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": "1.0",
        "conversation_id": "C0001",
        "utterance_id": 4,
        "masked_text": "[이름] 씨",
        "has_masked_data": True,
        "masked_types": ["PERSON"],
    }
    payload.update(overrides)
    return payload


def tuned_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": "1.0",
        "conversation_id": "C0001",
        "utterance_id": 4,
        "tuned_text": "[이름] 씨.",
        "is_tuned": True,
        "has_unclear": False,
        "unclear_segments": [],
    }
    payload.update(overrides)
    return payload


class LoaderTests(unittest.TestCase):
    def test_loads_valid_masked_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "masked_result0004.json"
            path.write_text(json.dumps(masked_payload()), encoding="utf-8")

            self.assertEqual(masked_payload(), load_masked_result(path))

    def test_loads_valid_tuned_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tuned_result0004.json"
            path.write_text(json.dumps(tuned_payload()), encoding="utf-8")

            self.assertEqual(tuned_payload(), load_tuned_result(path))

    def test_reports_missing_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            missing_path = Path(directory) / "missing.json"

            with self.assertRaises(FileNotFoundError):
                load_masked_result(missing_path)
            with self.assertRaises(FileNotFoundError):
                load_tuned_result(missing_path)

    def test_reports_malformed_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "broken.json"
            path.write_text("{not valid json", encoding="utf-8")

            with self.assertRaises(InputDataError):
                load_masked_result(path)
            with self.assertRaises(InputDataError):
                load_tuned_result(path)

    def test_reports_missing_required_masked_field(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "missing-field.json"
            payload = masked_payload()
            del payload["masked_types"]
            path.write_text(json.dumps(payload), encoding="utf-8")

            with self.assertRaises(InputDataError):
                load_masked_result(path)

    def test_reports_missing_required_tuned_field(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "missing-field.json"
            payload = tuned_payload()
            del payload["has_unclear"]
            path.write_text(json.dumps(payload), encoding="utf-8")

            with self.assertRaises(InputDataError):
                load_tuned_result(path)
