"""Regression checks for evidence precedence and validator failure behavior."""
import copy
import importlib.util
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "dataset/scripts/restore_pilot.py"
SPEC = importlib.util.spec_from_file_location("restore_pilot", SCRIPT)
pilot = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pilot)


class PilotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows, cls.manifest = pilot.restore()

    def test_evidence_precedence_and_patch(self):
        self.assertEqual(self.rows[2]["utterances"][9]["text"], pilot.PATCH_TEXT)
        self.assertFalse(self.rows[4]["utterances"][4]["is_phishing"])
        # Preserve the final JSON even though its prose summary says otherwise.
        self.assertTrue(self.rows[5]["utterances"][6]["is_phishing"])
        self.assertEqual(self.rows[5]["utterances"][6]["labels"], ["secrecy"])
        self.assertEqual(self.rows[5]["generation_model"], "GPT-6 (Codex)")
        self.assertEqual(self.rows[5]["revision_history"][-1]["revision_model"], "GPT-6 Luna")

    def test_recomputed_counts(self):
        counts = pilot.validate(self.rows)
        self.assertEqual((counts["phishing"], counts["normal"], counts["positive_labels"]), (34, 102, 37))

    def test_same_count_text_corruption_fails_evidence_comparison(self):
        rows = copy.deepcopy(self.rows)
        rows[2]["utterances"][9]["text"] = "잘 들립니다. 그래도 이 통화는 여기까지 하겠습니다."
        with self.assertRaisesRegex(ValueError, "TXT evidence"):
            pilot.validate(rows, self.rows)

    def test_invalid_metadata_ids_and_labels_fail(self):
        for key, value in (("review_status", "approved"), ("actual_call", True), ("split", "test")):
            rows = copy.deepcopy(self.rows)
            rows[0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                pilot.validate(rows)
        for key, value in (("utterance_id", True), ("utterance_id", 2), ("is_phishing", "false"),
                           ("labels", ["not_a_label"]), ("labels", ["app_installation", "app_installation"])):
            rows = copy.deepcopy(self.rows)
            rows[0]["utterances"][0][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                pilot.validate(rows)
        rows = copy.deepcopy(self.rows)
        rows[0]["utterances"][1]["labels"] = ["secrecy"]
        with self.assertRaisesRegex(ValueError, "Normal utterance"):
            pilot.validate(rows)

    def test_duplicate_json_keys_fail(self):
        with self.assertRaisesRegex(ValueError, "Duplicate JSON key"):
            pilot.parse_json('{"is_phishing": false, "is_phishing": true}')

    def test_tampered_source_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for filename in pilot.FILENAMES:
                (root / filename).write_bytes((pilot.SOURCES / filename).read_bytes())
            with (root / pilot.FILENAMES[0]).open("ab") as stream:
                stream.write(b"\nchanged")
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                pilot.restore(root)

    def test_unlisted_revision_changes_are_reported(self):
        changes = next(item for item in self.manifest["revision_differences"]
                       if item["synthetic_id"] == "SYN2-TRAIN-0006")
        self.assertIn(4, changes["unlisted_changed_ids"])
        self.assertIn(6, changes["unlisted_changed_ids"])


if __name__ == "__main__":
    unittest.main()
