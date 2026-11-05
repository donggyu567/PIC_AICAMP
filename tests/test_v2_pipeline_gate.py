"""Exercise explicit split/review gates without creating any approvals."""
import copy
import csv
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"dataset/scripts"))
import v2_pipeline_gate as gate
from audit_v2_pipeline import TRAIN, VALIDATION, REF, read_jsonl, compare, normalize


class PipelineGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.train, cls.val = read_jsonl(TRAIN), read_jsonl(VALIDATION)
        cls.reviews = []
        for relative in ("dataset/review/v2_pilot/human_review_working.csv", "dataset/review/v2_train_expansion/human_review_new8.csv"):
            with (ROOT/relative).open(encoding="utf-8-sig", newline="") as stream:
                cls.reviews.extend(csv.DictReader(stream))
        sys.path.insert(0, str(REF))
        from risk_speech_ai.training_data import TrainingSample
        from risk_speech_ai.labels import to_multi_hot
        cls.sample_type, cls.multi_hot = TrainingSample, staticmethod(to_multi_hot)

    def prepare(self, rows, split, mode="preflight", **kwargs):
        return gate.prepare_partition(rows, split=split, mode=mode,
            sample_type=self.sample_type, to_multi_hot=self.multi_hot, **kwargs)

    def test_train_preflight208_without_status_mutation(self):
        before = copy.deepcopy(self.train)
        p = self.prepare(self.train, "train")
        self.assertEqual(len(p.samples), 208)
        self.assertFalse(p.training_allowed)
        self.assertEqual(before, self.train)

    def test_validation_preflight192_not_training(self):
        p = self.prepare(self.val, "validation")
        self.assertEqual(len(p.samples), 192)
        self.assertFalse(p.training_allowed)

    def test_mixed_partition_rejected(self):
        with self.assertRaises(gate.PipelineGateError):
            self.prepare(self.train+self.val, "train")

    def test_validation_rejected_by_training_mode(self):
        with self.assertRaises(gate.PipelineGateError):
            self.prepare(self.val, "validation", "training")

    def test_train_requires_actual_review_evidence(self):
        with self.assertRaises(gate.PipelineGateError):
            self.prepare(self.train, "train", "training", reviews=self.reviews)

    def test_current_208_all_blocked_not_just72(self):
        result = gate.approval_audit(self.train, self.reviews)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["eligible_for_normal_training"], 0)
        self.assertEqual(result["fully_reviewed_utterances"], 0)
        self.assertEqual(result["reason_counts"]["review_not_approved:김해린"], 208)
        self.assertEqual(result["reason_counts"]["review_not_approved:임정윤"], 72)

    def test_original_single_reviewer_not_sufficient(self):
        with self.assertRaises(gate.PipelineGateError):
            self.prepare(self.train[:16], "train", "training", reviews=self.reviews[:136])

    def test_explicit_mode_is_required(self):
        with self.assertRaises(TypeError):
            gate.prepare_partition(self.train, split="train", sample_type=self.sample_type, to_multi_hot=self.multi_hot)

    def test_unrecognized_mode_rejected(self):
        with self.assertRaises(gate.PipelineGateError):
            self.prepare(self.train, "train", "ignore-review")

    def test_review_source_text_mismatch_rejected(self):
        rows = copy.deepcopy(self.reviews)
        rows[0]["발화_내용"] = "FAULT INJECTION ONLY"
        with self.assertRaises(gate.PipelineGateError):
            gate.approval_audit(self.train, rows)

    def test_duplicate_review_evidence_rejected(self):
        with self.assertRaises(gate.PipelineGateError):
            gate.approval_audit(self.train, self.reviews+[self.reviews[0]])

    def test_partial_review_coverage_rejected(self):
        with self.assertRaises(gate.PipelineGateError):
            gate.approval_audit(self.train, self.reviews[:-1])

    def test_utterance_order_and_masking_rejected(self):
        for field, value in (("utterance_id", True), ("text", "[UNSUPPORTED_MASK]"), ("is_phishing", False)):
            data = copy.deepcopy(self.train)
            data[0]["utterances"][0][field] = value
            with self.assertRaises(gate.PipelineGateError):
                self.prepare(data, "train")

    def test_history_never_crosses_conversation_boundary(self):
        for split, rows in (("train", self.train), ("validation", self.val)):
            p = self.prepare(rows, split)
            for sample in p.samples:
                c = next(c for c in rows if c["synthetic_id"] == sample.conversation_id)
                offset = sample.utterance_id-1
                self.assertEqual(sample.history_texts, [u["text"] for u in c["utterances"][max(0, offset-5):offset]])

    def test_legacy_builder_does_not_enforce_split_or_authorization(self):
        # Deliberately malformed standalone fixture, not current dataset labels
        # and not a claim that any human approved a real utterance.
        from risk_speech_ai.training_data import build_training_samples
        label = dict(conversation_id="TEST_FIXTURE_ONLY", utterance_id=1, split="validation", label_status="reviewed",
                     is_phishing=False, labels=[], final_approved=False, training_eligible=False)
        text = dict(conversation_id="TEST_FIXTURE_ONLY", utterance_id=1, tuned_text="fixture")
        self.assertEqual(len(build_training_samples([label], [text]).samples), 1)

    def test_threshold_screen_retains_exact_normalized_and_near(self):
        a = dict(id="a", text="abcdefghijklmnop", normalized=normalize("abcdefghijklmnop"))
        rows = [dict(id=str(i), text=t, normalized=normalize(t)) for i,t in enumerate((
            "abcdefghijklmnop", "abcd efgh,ijklmnop!", "abcdefghijklmnoq", "zzzzzzzzzzzzzzzz"))]
        r = compare([a], rows)
        self.assertEqual(r["pairs_checked"], 4)
        self.assertEqual(r["candidate_count"], 3)
        self.assertEqual(r["kinds"], {"exact": 1, "normalized_only": 1, "similar_at_080": 1})


if __name__ == "__main__":
    unittest.main()
