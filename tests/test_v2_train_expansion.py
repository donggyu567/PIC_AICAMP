"""Corruption rejection, protected output, and mixed-review exclusion checks."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "dataset/scripts"))
import prepare_v2_train_expansion as source
import validate_v2_train_expansion as audit


class TrainExpansionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = source.jsonl(source.PREVIOUS)

    def setUp(self):
        self.new = copy.deepcopy(source.CONVERSATIONS)
        self.old = copy.deepcopy(self.original)
        audit.CHECKS.clear()

    def reject(self):
        with self.assertRaises(ValueError):
            audit.validate_structure(self.new, self.old, self.old+self.new)

    def test_schema_and_mixed_review_pass(self):
        result = audit.validate_structure(self.new, self.old, self.old+self.new)
        self.assertEqual(result["merged24"]["utterances"], 208)
        self.assertEqual(result["new8"]["entirely_normal_conversations"], 4)

    def test_wrong_split_rejected(self):
        self.new[0]["split"] = "validation"
        self.reject()

    def test_id_collision_rejected(self):
        self.new[0]["synthetic_id"] = self.old[0]["synthetic_id"]
        self.reject()

    def test_utterance_order_rejected(self):
        self.new[0]["utterances"][1]["utterance_id"] = 1
        self.reject()

    def test_boolean_utterance_id_rejected(self):
        self.new[0]["utterances"][0]["utterance_id"] = True
        self.reject()

    def test_unknown_label_rejected(self):
        self.new[0]["utterances"][1]["labels"] = ["arbitrary_risk"]
        self.reject()

    def test_normal_with_positive_label_rejected(self):
        self.new[0]["utterances"][1]["is_phishing"] = False
        self.reject()

    def test_empty_rationale_rejected(self):
        self.new[0]["utterances"][0]["label_rationale"] = ""
        self.reject()

    def test_unknown_mask_rejected(self):
        self.new[0]["utterances"][0]["text"] += " [BANK_LOGIN]"
        self.reject()

    def test_literal_phone_rejected(self):
        self.new[0]["utterances"][0]["text"] += " 000-0000-0000"
        self.reject()

    def test_new_human_approval_rejected(self):
        self.new[0]["revision_history"][0]["human_approved"] = True
        self.reject()

    def test_old_review_edit_rejected(self):
        self.old[0]["review_preparation"]["reviewer_results"][0]["김해린"] = "승인"
        self.reject()

    def test_existing_file_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"review.csv"
            source.write_new(path, "human edits")
            with self.assertRaises(FileExistsError):
                source.write_new(path, "replacement")
            self.assertEqual(path.read_text(), "human edits")

    def test_duplicate_json_keys_rejected(self):
        with self.assertRaises(ValueError):
            json.loads('{"split":"train","split":"validation"}', object_pairs_hook=audit.no_duplicate_keys)

    def test_mixed_safe_builder_two_stage_statistics_and_context(self):
        sys.path.insert(0, str(audit.REFERENCE))
        from risk_speech_ai.training_data import TrainingSample
        from risk_speech_ai.train_cli import build_safe_training_samples
        from risk_speech_ai.labels import to_multi_hot
        merged = self.old+self.new
        before = copy.deepcopy(merged)
        samples, labels, texts, contexts = audit.dry_run_samples(merged, TrainingSample, to_multi_hot)
        safe, initial = build_safe_training_samples(labels, texts)
        self.assertEqual(len(samples), 208)
        self.assertEqual(len(safe.samples), 136)
        self.assertEqual(initial["excluded_unreviewed"], 72)
        self.assertEqual(safe.statistics["missing_tuned_text"], 72)
        self.assertEqual(safe.statistics["excluded_unreviewed"], 0)
        self.assertTrue(all(r["label_status"] == "unreviewed" for r in labels[136:]))
        self.assertTrue(all(r["label_status"] == "reviewed" for r in labels[:136]))
        self.assertTrue(all(r["training_authorized"] is False and r["training_eligible"] is False for r in labels))
        self.assertEqual(merged, before)
        for sample in samples:
            c = next(c for c in merged if c["synthetic_id"] == sample.conversation_id)
            offset = sample.utterance_id-1
            self.assertEqual(sample.history_texts, [u["text"] for u in c["utterances"][max(0, offset-5):offset]])
        self.assertEqual(contexts[136]["history_utterance_ids"], [])

    def test_dry_run_refuses_validation_mix(self):
        self.new[0]["split"] = "validation"
        with self.assertRaises(ValueError):
            audit.dry_run_samples(self.new, None, None)


if __name__ == "__main__":
    unittest.main()
