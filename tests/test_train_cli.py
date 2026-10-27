"""The data gate must not create a checkpoint or load model assets."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from risk_speech_ai.train_cli import build_safe_training_samples, main


class TrainCliTests(unittest.TestCase):
    def test_excluded_utterance_cannot_enter_history(self):
        labels = [
            {"conversation_id": "P1", "utterance_id": 1, "label_status": "unreviewed",
             "is_phishing": True, "labels": []},
            {"conversation_id": "P1", "utterance_id": 2, "label_status": "reviewed",
             "is_phishing": True, "labels": ["money_transfer"]},
        ]
        tuned = [
            {"conversation_id": "P1", "utterance_id": 1, "tuned_text": "excluded"},
            {"conversation_id": "P1", "utterance_id": 2, "tuned_text": "send money"},
        ]
        built, statistics = build_safe_training_samples(labels, tuned)
        self.assertEqual(1, statistics["excluded_unreviewed"])
        self.assertEqual(1, len(built.samples))
        self.assertEqual([], built.samples[0].history_texts)

    def test_validate_only_joins_reviewed_rows_without_training(self):
        with tempfile.TemporaryDirectory() as directory:
            labels = Path(directory) / "labels.jsonl"
            tuned = Path(directory) / "tuned.jsonl"
            labels.write_text(json.dumps({
                "conversation_id": "P1", "utterance_id": 1,
                "label_status": "reviewed", "is_phishing": True,
                "labels": ["money_transfer"],
            }) + "\n", encoding="utf-8")
            tuned.write_text(json.dumps({
                "conversation_id": "P1", "utterance_id": 1,
                "tuned_text": "Send money",
            }) + "\n", encoding="utf-8")
            with patch("risk_speech_ai.train_cli.load_koelectra_tokenizer") as tokenizer, \
                 patch("risk_speech_ai.train_cli.create_training_model") as model:
                result = main([
                    "--labels-jsonl", str(labels), "--tuned-jsonl", str(tuned),
                    "--data-version", "review-v1",
                ])
            self.assertEqual(0, result)
            tokenizer.assert_not_called()
            model.assert_not_called()


if __name__ == "__main__":
    unittest.main()
