import unittest

from risk_speech_ai.metrics import binary_metrics, multilabel_metrics


class MetricTests(unittest.TestCase):
    def test_binary_counts_auc_ap_and_brier(self):
        result = binary_metrics([0, 0, 1, 1], [0.1, 0.4, 0.35, 0.8])
        self.assertEqual([[2, 0], [1, 1]], result["confusion_matrix"])
        self.assertEqual((1, 2, 0, 1), tuple(result[key] for key in ("tp", "tn", "fp", "fn")))
        self.assertAlmostEqual(0.75, result["roc_auc"])
        self.assertAlmostEqual(5 / 6, result["average_precision"])
        self.assertAlmostEqual(2 / 3, result["f1"])
        self.assertAlmostEqual(0.158125, result["brier_score"])

    def test_tied_probabilities_and_undefined_classes(self):
        self.assertAlmostEqual(0.5, binary_metrics([0, 1], [0.5, 0.5])["roc_auc"])
        all_negative = binary_metrics([0, 0], [0.1, 0.2])
        self.assertIsNone(all_negative["roc_auc"])
        self.assertIsNone(all_negative["average_precision"])
        self.assertIsNone(all_negative["recall"])
        self.assertEqual("no_actual_positive", all_negative["undefined_reasons"]["recall"])
        all_positive = binary_metrics([1, 1], [0.2, 0.7])
        self.assertIsNone(all_positive["roc_auc"])
        self.assertEqual(1.0, all_positive["average_precision"])

    def test_multilabel_aggregation_and_zero_support(self):
        y = [[1, 0, 0, 0, 0, 0, 0, 0], [0, 1, 0, 0, 0, 0, 0, 0]]
        p = [[0.9, 0.6, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1],
             [0.2, 0.8, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1]]
        result = multilabel_metrics(y, p)
        self.assertAlmostEqual(0.8, result["micro"]["f1"])
        self.assertAlmostEqual(1 / 16, result["hamming_loss"])
        self.assertAlmostEqual(0.5, result["exact_match_ratio"])
        self.assertEqual(2, result["macro"]["defined_f1_labels"])
        self.assertIsNone(result["per_label"]["app_installation"]["roc_auc"])


if __name__ == "__main__":
    unittest.main()
