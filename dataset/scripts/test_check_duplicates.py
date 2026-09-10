"""Tests for the raw-data duplicate checker."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).with_name("check_duplicates.py")
SPEC = importlib.util.spec_from_file_location("check_duplicates", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
check_duplicates = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = check_duplicates
SPEC.loader.exec_module(check_duplicates)


class DuplicateCheckerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.raw_dir = self.root / "raw"
        self.registry = self.root / "source_registry.csv"
        self.registry.write_text(
            "source_id,source_name,source_url,data_type\n"
            "S001,source,https://example.test/source,phishing\n",
            encoding="utf-8",
        )
        self.conversation_registry = self.root / "conversation_registry.csv"
        self.write_conversation_registry([])

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def write_utterance(self, conversation_id: str, utterance_id: int, text: str) -> None:
        category = "phishing" if conversation_id.startswith("P") else "normal"
        path = self.raw_dir / category / conversation_id / f"utterance_{utterance_id:03}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "conversation_id": conversation_id,
                    "utterance_id": utterance_id,
                    "text": text,
                    "source": "source",
                }
            ),
            encoding="utf-8",
        )

    def write_conversation_registry(self, rows: list[list[str]]) -> None:
        header = (
            "conversation_id,source_id,source_item_id,data_type,assignee,status,"
            "utterance_count,notes\n"
        )
        body = "".join(",".join(row) + "\n" for row in rows)
        self.conversation_registry.write_text(header + body, encoding="utf-8")

    def test_shared_utterance_does_not_make_conversations_an_error(self) -> None:
        self.write_utterance("P0001", 1, "같은 문장")
        self.write_utterance("P0002", 1, "같은 문장")
        self.write_utterance("P0002", 2, "다른 문장")

        exit_code, output = check_duplicates.run_check(self.raw_dir, self.registry)

        self.assertEqual(0, exit_code)
        self.assertIn("Exact utterance duplicate groups: 1", output)
        self.assertIn("Exact duplicate conversations: 0", output)

    def test_identical_transcripts_with_different_ids_are_an_error(self) -> None:
        self.write_utterance("P0001", 1, "첫 문장")
        self.write_utterance("P0001", 2, "둘째 문장")
        self.write_utterance("P0002", 1, "첫 문장")
        self.write_utterance("P0002", 2, "둘째 문장")

        exit_code, output = check_duplicates.run_check(self.raw_dir, self.registry)

        self.assertEqual(1, exit_code)
        self.assertIn("[ERROR] Duplicate conversation detected", output)

    def test_spacing_and_punctuation_only_transcript_difference_is_an_error(self) -> None:
        self.write_utterance("P0001", 1, "Hello,   World!")
        self.write_utterance("P0002", 1, "hello world")

        exit_code, output = check_duplicates.run_check(self.raw_dir, self.registry)

        self.assertEqual(1, exit_code)
        self.assertIn("Exact duplicate conversations: 1", output)

    def test_similar_transcript_is_a_warning(self) -> None:
        self.write_utterance("P0001", 1, "abcdefghij")
        self.write_utterance("P0002", 1, "abcdefghi")

        exit_code, output = check_duplicates.run_check(self.raw_dir, self.registry)

        self.assertEqual(0, exit_code)
        self.assertIn("[WARNING] Similar conversation candidate", output)

    def test_only_raw_directory_is_scanned(self) -> None:
        self.write_utterance("P0001", 1, "원본")
        processed = self.root / "processed"
        processed.mkdir()
        (processed / "duplicate.json").write_text(
            json.dumps({"conversation_id": "P0002", "text": "원본"}),
            encoding="utf-8",
        )

        exit_code, output = check_duplicates.run_check(self.raw_dir, self.registry)

        self.assertEqual(0, exit_code)
        self.assertIn("Utterances scanned: 1", output)

    def test_shared_source_with_different_source_items_is_valid(self) -> None:
        self.write_conversation_registry(
            [
                ["P0001", "S001", "item-1", "phishing", "", "reserved", "", ""],
                ["P0002", "S001", "item-2", "phishing", "", "reserved", "", ""],
            ]
        )

        exit_code, output = check_duplicates.run_check(
            self.raw_dir, self.registry, self.conversation_registry
        )

        self.assertEqual(0, exit_code)
        self.assertIn("Errors: 0", output)

    def test_duplicate_source_item_is_an_error(self) -> None:
        self.write_conversation_registry(
            [
                ["P0001", "S001", "item-1", "phishing", "", "reserved", "", ""],
                ["P0002", "S001", "item-1", "phishing", "", "reserved", "", ""],
            ]
        )

        exit_code, output = check_duplicates.run_check(
            self.raw_dir, self.registry, self.conversation_registry
        )

        self.assertEqual(1, exit_code)
        self.assertIn("duplicate source_id/source_item_id", output)

    def test_unknown_source_and_mismatched_data_type_are_errors(self) -> None:
        self.write_conversation_registry(
            [
                ["P0001", "S999", "item-1", "phishing", "", "reserved", "", ""],
                ["P0002", "S001", "item-2", "normal", "", "reserved", "", ""],
            ]
        )

        exit_code, output = check_duplicates.run_check(
            self.raw_dir, self.registry, self.conversation_registry
        )

        self.assertEqual(1, exit_code)
        self.assertIn("unknown source_id S999", output)
        self.assertIn("does not match source S001", output)

    def test_reserved_row_without_conversation_id_is_valid(self) -> None:
        self.write_conversation_registry(
            [["", "S001", "", "phishing", "", "reserved", "", ""]]
        )

        exit_code, output = check_duplicates.run_check(
            self.raw_dir, self.registry, self.conversation_registry
        )

        self.assertEqual(0, exit_code)

    def test_duplicate_conversation_id_is_an_error(self) -> None:
        self.write_conversation_registry(
            [
                ["P0001", "S001", "item-1", "phishing", "", "reserved", "", ""],
                ["P0001", "S001", "item-2", "phishing", "", "reserved", "", ""],
            ]
        )

        exit_code, output = check_duplicates.run_check(
            self.raw_dir, self.registry, self.conversation_registry
        )

        self.assertEqual(1, exit_code)
        self.assertIn("duplicate conversation_id P0001", output)


if __name__ == "__main__":
    unittest.main()
