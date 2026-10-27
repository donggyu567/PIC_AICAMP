import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from risk_speech_ai.training_log import TrainingJournal


class JournalTests(unittest.TestCase):
    def test_each_record_is_flushed_and_existing_log_survives_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            with TrainingJournal(Path(directory), {"data_version": "fixture"}) as journal:
                journal.log_batch({"global_step": 1, "total_loss": 1.25})
                self.assertEqual(1, len(journal.path.joinpath("batches.jsonl").read_text().splitlines()))
                with patch.object(TrainingJournal, "_append", side_effect=OSError("disk failed")):
                    with self.assertRaisesRegex(OSError, "disk failed"):
                        journal.log_batch({"global_step": 2})
                journal.log_epoch({"epoch": 1, "average_total_loss": 1.25})
                location = journal.path
            rows = [json.loads(line) for line in (location / "batches.jsonl").read_text().splitlines()]
            self.assertEqual([1], [row["global_step"] for row in rows])
            self.assertEqual(1, len((location / "epochs.jsonl").read_text().splitlines()))


if __name__ == "__main__":
    unittest.main()
