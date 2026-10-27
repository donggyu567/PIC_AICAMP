import unittest

from risk_speech_ai.splits import plan_conversation_splits


class SplitTests(unittest.TestCase):
    def test_source_item_and_identical_text_cannot_cross_splits(self):
        labels = [
            {"conversation_id": "P0001", "source": "A", "source_item": "original-1"},
            {"conversation_id": "P0002", "source": "B", "source_item": "original-1"},
            {"conversation_id": "P0003", "source": "C", "source_item": "original-3"},
            {"conversation_id": "P0004", "source": "D", "source_item": "original-4"},
            {"conversation_id": "P0005", "source": "E", "source_item": "original-5"},
        ]
        tuned = [{"conversation_id": key, "tuned_text": text} for key, text in
                 (("P0001", "same"), ("P0002", "other"),
                  ("P0003", "same"), ("P0004", "distinct"), ("P0005", "another"))]
        result = plan_conversation_splits(labels, tuned, data_version="future-v1", group_by_source=False)
        assignment = result["conversation_to_split"]
        self.assertEqual(assignment["P0001"], assignment["P0002"])
        self.assertEqual(assignment["P0001"], assignment["P0003"])
        self.assertEqual(5, sum(result["utterance_counts"].values()))

    def test_invalid_ratios_rejected(self):
        with self.assertRaises(ValueError):
            plan_conversation_splits([{"conversation_id": "P0001"}], [],
                                     data_version="future-v1", ratios=(0.8, 0.2, 0.2))


if __name__ == "__main__":
    unittest.main()
