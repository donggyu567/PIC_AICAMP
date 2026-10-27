"""Tests for safe and idempotent tuned-result JSON persistence."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from models.llm_correction import (
    CorrectionOutputConflictError,
    CorrectionOutputError,
    CorrectionResult,
    CorrectionResultStore,
    MaskedTranscript,
)


def correction_result(
    *,
    conversation_id: str = "C0001",
    utterance_id: int = 17,
    tuned_text: str = "[PERSON] 씨, 지금 송금하세요.",
) -> CorrectionResult:
    return CorrectionResult(
        schema_version="1.0",
        conversation_id=conversation_id,
        utterance_id=utterance_id,
        tuned_text=tuned_text,
        is_tuned=True,
        has_unclear=False,
        unclear_segments=(),
    )


def masked_transcript(
    *,
    conversation_id: str = "C0001",
    utterance_id: int = 17,
    masked_text: str = "[PERSON] 씨 지금 송금하세요.",
) -> MaskedTranscript:
    return MaskedTranscript(
        schema_version="1.0",
        conversation_id=conversation_id,
        utterance_id=utterance_id,
        masked_text=masked_text,
        has_masked_data="[PERSON]" in masked_text,
        masked_types=("PERSON",) if "[PERSON]" in masked_text else (),
    )


class CorrectionResultStoreTests(unittest.TestCase):
    def test_saves_utf8_json_with_the_expected_name_and_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            store = CorrectionResultStore(temporary_directory)
            result = correction_result()

            output_path = store.save(result)
            payload = json.loads(output_path.read_text(encoding="utf-8"))

            self.assertEqual("tuned_result0017.json", output_path.name)
            self.assertEqual(result.to_dict(), payload)
            self.assertIn("씨", output_path.read_text(encoding="utf-8"))
            self.assertNotIn("raw_text", payload)
            self.assertNotIn("masked_text", payload)

    def test_does_not_truncate_utterance_ids_over_four_digits(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            store = CorrectionResultStore(temporary_directory)

            output_path = store.save(correction_result(utterance_id=10_000))

            self.assertEqual("tuned_result10000.json", output_path.name)

    def test_separates_conversations_with_the_same_utterance_id(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            store = CorrectionResultStore(temporary_directory)

            first_path = store.save(correction_result(conversation_id="C0001"))
            second_path = store.save(correction_result(conversation_id="C0002"))

            self.assertNotEqual(first_path.parent, second_path.parent)
            self.assertTrue(first_path.exists())
            self.assertTrue(second_path.exists())

    def test_hashes_path_like_conversation_ids_inside_the_output_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            store = CorrectionResultStore(root)
            dangerous_id = "../../outside\\CON:C"

            output_path = store.save(
                correction_result(conversation_id=dangerous_id)
            )

            self.assertEqual(
                os.path.commonpath((str(root), str(output_path.resolve()))),
                str(root),
            )
            self.assertRegex(
                output_path.parent.name,
                r"^conversation-[0-9a-f]{64}$",
            )
            self.assertNotIn(dangerous_id, str(output_path))

    def test_returns_the_existing_path_for_an_identical_result(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            store = CorrectionResultStore(temporary_directory)
            result = correction_result()
            first_path = store.save(result)
            original_bytes = first_path.read_bytes()

            with patch("models.llm_correction.output.os.link") as link:
                second_path = store.save(result)

            link.assert_not_called()
            self.assertEqual(first_path, second_path)
            self.assertEqual(original_bytes, second_path.read_bytes())

    def test_rejects_a_different_result_without_overwriting(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            store = CorrectionResultStore(temporary_directory)
            first_path = store.save(correction_result())
            original_bytes = first_path.read_bytes()

            with self.assertRaisesRegex(
                CorrectionOutputConflictError,
                "different correction result",
            ):
                store.save(
                    correction_result(
                        tuned_text="[PERSON] 씨, 지금 바로 송금하세요."
                    )
                )

            self.assertEqual(original_bytes, first_path.read_bytes())

    def test_loads_a_result_matching_the_original_transcript(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            store = CorrectionResultStore(temporary_directory)
            expected = correction_result()
            store.save(expected)

            loaded = store.load(masked_transcript())

            self.assertEqual(expected, loaded)

    def test_returns_none_when_a_result_does_not_exist(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            store = CorrectionResultStore(temporary_directory)

            self.assertIsNone(store.load(masked_transcript()))

    def test_returns_existing_result_for_the_same_idempotency_key(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            store = CorrectionResultStore(temporary_directory)
            expected = correction_result()
            store.save(expected)

            loaded = store.load(
                masked_transcript(masked_text="완전히 다른 문장입니다.")
            )

            self.assertEqual(expected, loaded)

    def test_does_not_replace_a_malformed_existing_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            store = CorrectionResultStore(temporary_directory)
            result = correction_result()
            output_path = store.save(result)
            output_path.write_text("{broken", encoding="utf-8")

            with self.assertRaisesRegex(
                CorrectionOutputError,
                "not valid JSON",
            ):
                store.save(result)

            self.assertEqual("{broken", output_path.read_text(encoding="utf-8"))

    def test_removes_the_temporary_file_when_publishing_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            store = CorrectionResultStore(temporary_directory)

            with patch(
                "models.llm_correction.output.os.link",
                side_effect=OSError,
            ):
                with self.assertRaisesRegex(
                    CorrectionOutputError,
                    "cannot be stored",
                ):
                    store.save(correction_result())

            root = Path(temporary_directory)
            self.assertEqual([], list(root.rglob("*.tmp")))
            self.assertEqual([], list(root.rglob("tuned_result*.json")))

    def test_returns_the_committed_result_if_temp_cleanup_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            store = CorrectionResultStore(temporary_directory)

            with patch("pathlib.Path.unlink", side_effect=OSError):
                output_path = store.save(correction_result())

            self.assertTrue(output_path.exists())
            self.assertEqual(
                correction_result().to_dict(),
                json.loads(output_path.read_text(encoding="utf-8")),
            )

    def test_rejects_the_wrong_application_type(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            store = CorrectionResultStore(temporary_directory)

            with self.assertRaisesRegex(TypeError, "CorrectionResult"):
                store.save({"utterance_id": 17})


if __name__ == "__main__":
    unittest.main()
