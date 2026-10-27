"""Raw-logit conversion, threshold, and checkpoint inference contracts."""

import math
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path

import torch

from risk_speech_ai.inference import (
    InferenceInput, ThresholdConfig, infer_batch, load_checkpoint_inference,
    logits_to_outputs,
)
from risk_speech_ai.labels import LABELS, NUM_LABELS
from risk_speech_ai.model import ModelOutput
from risk_speech_ai.tokenization import InputTooLongError
from risk_speech_ai.training import TrainingConfig, train_model
from risk_speech_ai.training_data import TrainingSample
from test_dataset import SmallPairTokenizer
from test_training import tiny_model


class OutputTests(unittest.TestCase):
    def test_zero_logits_give_50_and_inclusive_default_threshold(self):
        results = logits_to_outputs(ModelOutput(torch.zeros((1, 1)), torch.zeros((1, NUM_LABELS))))
        self.assertEqual(1, len(results))
        result = results[0]
        self.assertEqual(0.5, result.risk_probability)
        self.assertEqual(50.0, result.risk_score)
        self.assertEqual(list(LABELS), list(result.type_scores))
        self.assertEqual(list(LABELS), list(result.type_probabilities))
        self.assertEqual([50.0] * NUM_LABELS, list(result.type_scores.values()))
        self.assertEqual(list(LABELS), result.detected_types)
        self.assertEqual(ThresholdConfig().version, "initial-0.5")

    def test_multiple_types_empty_types_and_label_specific_thresholds(self):
        logits = ModelOutput(
            torch.tensor([[10.0], [10.0]]),
            torch.tensor([
                [2.0, 2.0] + [-2.0] * 6,
                [-2.0] * 8,
            ]),
        )
        thresholds = ThresholdConfig(
            values={**ThresholdConfig().values, "money_transfer": 0.9},
            version="experiment-1",
        )
        results = logits_to_outputs(logits, thresholds)
        self.assertEqual(["institution_impersonation"], results[0].detected_types)
        self.assertEqual([], results[1].detected_types)
        self.assertGreater(results[1].risk_score, 99)
        self.assertTrue(all(0 <= item.risk_score <= 100 for item in results))
        self.assertTrue(all(0 <= score <= 100 for item in results
                            for score in item.type_scores.values()))
        self.assertEqual(2, len(logits_to_outputs(logits)[0].detected_types))
        self.assertAlmostEqual(100 * results[0].type_probabilities["money_transfer"],
                               results[0].type_scores["money_transfer"])

    def test_probability_is_compared_before_display_rounding(self):
        values = {label: 0.5 for label in LABELS}
        values["money_transfer"] = 0.50001
        thresholds = ThresholdConfig(values, version="precision-test")
        logits = ModelOutput(torch.zeros((1, 1)), torch.zeros((1, NUM_LABELS)))
        result = logits_to_outputs(logits, thresholds)[0]
        self.assertEqual(50.0, result.type_scores["money_transfer"])
        self.assertNotIn("money_transfer", result.detected_types)

    def test_threshold_config_rejects_drift_and_invalid_values(self):
        for values in (
            {"money_transfer": 0.5},
            {**ThresholdConfig().values, "unknown": 0.5},
            {**ThresholdConfig().values, "secrecy": -0.1},
            {**ThresholdConfig().values, "secrecy": 1.1},
            {**ThresholdConfig().values, "secrecy": float("nan")},
        ):
            with self.subTest(values=values), self.assertRaises(ValueError):
                ThresholdConfig(values)
        values = dict(ThresholdConfig().values)
        config = ThresholdConfig(values)
        values["money_transfer"] = 0.9
        self.assertEqual(0.5, config.values["money_transfer"])
        with self.assertRaisesRegex(ValueError, "distinct version"):
            ThresholdConfig(values)

    def test_invalid_logits_fail_and_output_is_plain_schema(self):
        for output in (
            ModelOutput(torch.zeros(1), torch.zeros((1, NUM_LABELS))),
            ModelOutput(torch.zeros((2, 1)), torch.zeros((1, NUM_LABELS))),
            ModelOutput(torch.full((1, 1), float("nan")), torch.zeros((1, NUM_LABELS))),
        ):
            with self.subTest(shape=tuple(output.risk_logits.shape)), self.assertRaises(ValueError):
                logits_to_outputs(output)
        plain = asdict(logits_to_outputs(ModelOutput(
            torch.zeros((1, 1)), torch.zeros((1, NUM_LABELS))
        ))[0])
        self.assertEqual({"risk_score", "risk_probability", "type_scores",
                          "type_probabilities", "detected_types"}, set(plain))


class ForwardTests(unittest.TestCase):
    def test_shared_tokenizer_batch_eval_and_no_grad(self):
        class FixedModel(torch.nn.Module):
            def __init__(self):
                super().__init__()
                self.weight = torch.nn.Parameter(torch.tensor(1.0))
                self.shape = None

            def forward(self, input_ids, attention_mask, token_type_ids):
                self.shape = tuple(input_ids.shape)
                self.assertions = (not self.training, not torch.is_grad_enabled())
                self.segments = token_type_ids.detach().clone()
                self.mask = attention_mask.detach().clone()
                batch = input_ids.shape[0]
                return ModelOutput(
                    self.weight.expand(batch, 1),
                    torch.zeros((batch, NUM_LABELS), device=input_ids.device),
                )

        model = FixedModel().train()
        result = infer_batch(model, [
            InferenceInput([], "short"),
            InferenceInput(["long history"], "current has more words"),
        ], tokenizer=SmallPairTokenizer(), device="cpu")
        self.assertEqual(2, len(result))
        self.assertTrue(all(model.assertions))
        self.assertEqual((2, 9), model.shape)
        self.assertTrue((model.mask[0] == 0).any())
        self.assertTrue((model.segments[1] == 1).any())
        self.assertFalse(model.training)
        self.assertTrue(all(isinstance(value, float) for value in
                            [result[0].risk_score, *result[0].type_scores.values()]))
        self.assertEqual([], infer_batch(model, [], tokenizer=SmallPairTokenizer()))

    def test_current_only_overflow_is_propagated(self):
        with self.assertRaises(InputTooLongError):
            infer_batch(tiny_model(), [InferenceInput([], " ".join(["word"] * 510))],
                        tokenizer=SmallPairTokenizer())


class CheckpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.addClassCleanup(torch.set_num_threads, torch.get_num_threads())
        torch.set_num_threads(1)

    def test_trained_synthetic_checkpoint_restores_for_inference(self):
        tokenizer = SmallPairTokenizer()
        model = tiny_model()
        sample = TrainingSample("P0001", 1, [], "send money", 1.0,
                                [0, 1, 0, 0, 0, 0, 0, 0])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "last.pt"
            train_model(model, [sample], tokenizer,
                        TrainingConfig(data_version="synthetic", epochs=1, batch_size=1,
                                       learning_rate=1e-3),
                        checkpoint_path=path, device="cpu")
            thresholds = ThresholdConfig(version="threshold-v1")
            session = load_checkpoint_inference(
                path, tokenizer=tokenizer, thresholds=thresholds,
                model=tiny_model(), device="cpu",
            )
            self.assertEqual("synthetic", session.training_metadata["data_version"])
            self.assertEqual("threshold-v1", session.thresholds.version)
            outputs = session.predict([InferenceInput([], "send money")])
            self.assertEqual(1, len(outputs))
            self.assertTrue(math.isfinite(outputs[0].risk_score))
            self.assertEqual(list(LABELS), list(outputs[0].type_scores))
            self.assertFalse(session.model.training)

            bad_path = Path(directory) / "wrong-labels.pt"
            checkpoint = torch.load(path, weights_only=True)
            checkpoint["label_order"] = list(reversed(LABELS))
            torch.save(checkpoint, bad_path)
            with self.assertRaisesRegex(ValueError, "label order"):
                load_checkpoint_inference(bad_path, tokenizer=tokenizer,
                                          model=tiny_model(), device="cpu")


if __name__ == "__main__":
    unittest.main()
