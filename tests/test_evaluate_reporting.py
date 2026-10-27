import tempfile
import unittest
from pathlib import Path

from risk_speech_ai.evaluate_cli import _markdown, _svg_charts
from risk_speech_ai.metrics import binary_metrics, multilabel_metrics


class ReportingTests(unittest.TestCase):
    def test_aggregate_reports_render_without_utterance_text(self):
        targets = [[1] * 8, [0] * 8]
        probabilities = [[0.8] * 8, [0.2] * 8]
        metrics = {"risk": binary_metrics([1, 0], [0.8, 0.2]),
                   "types": multilabel_metrics(targets, probabilities)}
        history = {"batch_cumulative_observations": [
            {"global_step": 1, "running_loss": 1.2},
            {"global_step": 2, "running_loss": 0.9}],
            "epoch_losses": [{"average_total_loss": 0.9,
                              "average_risk_loss": 0.5, "average_type_loss": 0.4}]}
        benchmark = {"loading": {"model_load_seconds": 1.0},
                     "cold_single_utterance_ms": 3.0,
                     "warm_single_utterance": {"n": 3, "mean_ms": 2.0,
                                               "p50_ms": 2.0, "p95_ms": 2.2},
                     "full_train_evaluation": {"utterances_per_second": 20.0},
                     "observed_peak_working_set_bytes": 1024}
        benchmark["memory_measurement"] = "fixture observation"
        reproducibility = {"data_version": "fixture", "data_commit": "abc",
                           "checkpoint": {"sha256": "deadbeef"}}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _svg_charts(root, metrics, history)
            report = _markdown(metrics, benchmark, reproducibility, history)
            self.assertIn("TRAIN (IN-SAMPLE)", report)
            self.assertTrue((root / "loss_trend.svg").exists())
            self.assertTrue((root / "risk_confusion.svg").exists())
            self.assertTrue((root / "per_label_f1.svg").exists())


if __name__ == "__main__":
    unittest.main()
