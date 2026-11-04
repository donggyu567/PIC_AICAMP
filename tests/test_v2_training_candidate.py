"""The single-review adapter must preserve labels, context and split boundaries."""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "dataset/scripts"))
import prepare_v2_training_candidate as prep


class CandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.candidates, cls.reviews = prep.load_reviewed_candidates()
        cls.builder, cls.labels = prep.load_reference()

    def test_opt_in_required(self):
        with self.assertRaisesRegex(ValueError, "opt-in"):
            prep.convert_candidates(self.candidates)

    def test_actual_builder_preserves_all_targets_and_histories(self):
        labels, tuned, metadata = prep.convert_candidates(self.candidates, allow_single_review_candidate=True)
        built = self.builder.build_training_samples(labels, tuned)
        self.assertEqual(len(built.samples), 136)
        self.assertEqual(sum(s.risk_target for s in built.samples), 34)
        self.assertEqual(sum(sum(s.type_targets) for s in built.samples), 37)
        self.assertEqual(len(metadata), 16)
        for c in self.candidates:
            samples = [s for s in built.samples if s.conversation_id == c["synthetic_id"]]
            for index, sample in enumerate(samples):
                self.assertEqual(sample.current_text, c["utterances"][index]["text"])
                self.assertEqual(sample.history_texts, [u["text"] for u in c["utterances"][max(0, index-5):index]])
                self.assertEqual(sample.type_targets, self.labels.to_multi_hot(c["utterances"][index]["labels"]))

    def test_validation_or_test_cannot_enter_train(self):
        for split in ("validation", "test"):
            candidates = copy.deepcopy(self.candidates)
            candidates[0]["split"] = split
            with self.subTest(split=split), self.assertRaisesRegex(ValueError, "TRAIN"):
                prep.convert_candidates(candidates, allow_single_review_candidate=True)

    def test_unreviewed_context_rejected(self):
        candidates = copy.deepcopy(self.candidates)
        candidates[0]["review_preparation"]["reviewer_results"][0]["임정윤"] = "미승인"
        with self.assertRaisesRegex(ValueError, "Unreviewed target/history"):
            prep.convert_candidates(candidates, allow_single_review_candidate=True)

    def test_final_approval_not_manufactured(self):
        for c in self.candidates:
            self.assertFalse(c["review_preparation"]["final_approved"])
            self.assertTrue(all(u["김해린"] == "미승인" and u["final_agreement"] == "미승인"
                                for u in c["review_preparation"]["reviewer_results"]))
        self.assertTrue(all(not row["검수_일시_임정윤"] for row in self.reviews))

    def test_duplicate_and_out_of_order_conversations_rejected(self):
        candidates = copy.deepcopy(self.candidates)
        candidates.append(candidates[0])
        with self.assertRaisesRegex(ValueError, "Duplicate conversation"):
            prep.convert_candidates(candidates, allow_single_review_candidate=True)
        candidates = copy.deepcopy(self.candidates)
        candidates[0]["utterances"].reverse()
        with self.assertRaisesRegex(ValueError, "Nonconsecutive"):
            prep.convert_candidates(candidates, allow_single_review_candidate=True)


if __name__ == "__main__":
    unittest.main()
