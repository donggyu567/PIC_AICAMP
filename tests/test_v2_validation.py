"""Reject corrupt validation artifacts and prevent false review promotion.

These tests mutate in-memory copies only; canonical data and review CSVs are
never edited by a test. Real DataLoader validation has its own executable audit.
"""
import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "dataset/scripts"))
import generate_v2_validation as generated
import validate_v2_validation as audit


class ValidationAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.train = [json.loads(line) for line in audit.TRAIN.read_text(encoding="utf-8").splitlines()]
        cls.registry = audit.read_json(audit.DATA / "scenario_registry.json")

    def setUp(self):
        self.data = copy.deepcopy(generated.CONVERSATIONS)
        audit.CHECKS.clear()

    def reject(self):
        with self.assertRaises(ValueError):
            audit.validate_structure(self.data, self.train, self.registry)

    def test_generated_schema_passes(self):
        result = audit.validate_structure(self.data, self.train, self.registry)
        self.assertEqual((result["conversations"], result["utterances"]), (24, 192))

    def test_wrong_split_rejected(self):
        self.data[0]["split"] = "train"
        self.reject()

    def test_duplicate_conversation_rejected(self):
        self.data[1]["synthetic_id"] = self.data[0]["synthetic_id"]
        self.reject()

    def test_duplicate_utterance_order_rejected(self):
        self.data[0]["utterances"][1]["utterance_id"] = 1
        self.reject()

    def test_unknown_label_rejected(self):
        self.data[0]["utterances"][1]["labels"] = ["unknown_risk"]
        self.reject()

    def test_normal_positive_contradiction_rejected(self):
        self.data[0]["utterances"][1]["is_phishing"] = False
        self.reject()

    def test_empty_rationale_rejected(self):
        self.data[0]["utterances"][0]["label_rationale"] = ""
        self.reject()

    def test_fake_human_approval_rejected(self):
        self.data[0]["revision_history"][0]["human_approved"] = True
        self.reject()

    def test_unapproved_mask_token_rejected(self):
        self.data[0]["utterances"][0]["text"] += " [SECRET_PHONE]"
        self.reject()

    def test_literal_identifier_rejected(self):
        # Safe non-real dummy number still must not bypass masking rules.
        self.data[0]["utterances"][0]["text"] += " 000-0000-0000"
        self.reject()

    def test_duplicate_json_keys_rejected(self):
        with self.assertRaises(ValueError):
            json.loads('{"split":"train","split":"validation"}', object_pairs_hook=audit.no_duplicate_keys)

    def test_evaluation_adapter_retains_unreviewed_and_training_excludes(self):
        sys.path.insert(0, str(audit.REFERENCE))
        from risk_speech_ai.training_data import TrainingSample, build_training_samples
        from risk_speech_ai.labels import to_multi_hot
        before = copy.deepcopy(self.data)
        samples, labels, texts, history = audit.evaluation_samples(self.data, TrainingSample, to_multi_hot)
        self.assertEqual(len(samples), 192)
        self.assertTrue(all(r["label_status"] == "unreviewed" and r["training_eligible"] is False
                            and r["split"] == "validation" and r["final_approved"] is False for r in labels))
        built = build_training_samples(labels, texts)
        self.assertEqual(built.samples, [])
        self.assertEqual(built.statistics["excluded_unreviewed"], 192)
        self.assertEqual(self.data, before)
        self.assertEqual(history[8]["history_utterance_ids"], [])

    def test_evaluation_adapter_refuses_train(self):
        self.data[0]["split"] = "train"
        with self.assertRaises(ValueError):
            audit.evaluation_samples(self.data, None, None)


if __name__ == "__main__":
    unittest.main()
