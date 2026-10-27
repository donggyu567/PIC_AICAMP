import unittest

import numpy as np

from risk_speech_ai.type_diagnostics import distribution_row, threshold_rows


class TypeDiagnosticsTests(unittest.TestCase):
    def test_threshold_sweep_counts_and_tie_rule(self):
        targets = np.array([1, 0, 1, 0])
        probabilities = np.array([0.31, 0.29, 0.18, 0.05])
        rows = threshold_rows(targets, probabilities, "example")
        self.assertEqual(46, len(rows))
        self.assertEqual((2, 1, 1, 1),
                         (rows[15]["positive_predictions"], rows[15]["tp"],
                          rows[15]["fp"], rows[15]["fn"]))
        self.assertEqual(0, rows[-1]["positive_predictions"])
        self.assertEqual(0.0, rows[-1]["f1"])

    def test_distribution_separates_actual_classes(self):
        row = distribution_row(np.array([1, 1, 0, 0]),
                               np.array([0.4, 0.3, 0.2, 0.1]), "example")
        self.assertEqual((2, 2), (row["positive"], row["negative"]))
        self.assertAlmostEqual(0.2, row["mean_gap_positive_minus_negative"])
        self.assertEqual(0, row["count_ge_0.5"])
        self.assertEqual(1.0, row["roc_auc"])


if __name__ == "__main__":
    unittest.main()
