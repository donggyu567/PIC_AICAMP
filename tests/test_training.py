"""Loss and short synthetic fine-tuning contracts."""

import math
import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import torch
from transformers import ElectraConfig, ElectraModel

from risk_speech_ai.config import BASE_MODEL_NAME
from risk_speech_ai.labels import LABELS
from risk_speech_ai.model import ModelOutput, RiskSpeechClassifier
from risk_speech_ai.training import (
    TrainingConfig, compute_losses, create_training_model, load_training_checkpoint, set_training_seed,
    train_model,
)
from risk_speech_ai.training_data import TrainingSample
from test_dataset import SmallPairTokenizer


def tiny_model():
    config = ElectraConfig(vocab_size=100, embedding_size=16, hidden_size=16,
                           num_hidden_layers=1, num_attention_heads=2,
                           intermediate_size=32, max_position_embeddings=512,
                           type_vocab_size=2)
    return RiskSpeechClassifier(encoder=ElectraModel(config))


class LossTests(unittest.TestCase):
    def test_raw_logits_mean_reduction_and_weighted_sum(self):
        logits = ModelOutput(
            risk_logits=torch.tensor([[2.0], [-2.0]], requires_grad=True),
            type_logits=torch.tensor([[2.0] * 8, [-2.0] * 8], requires_grad=True),
        )
        risk = torch.tensor([[1.0], [0.0]])
        types = torch.tensor([[1.0] * 8, [0.0] * 8])
        losses = compute_losses(logits, risk, types)
        criterion = torch.nn.BCEWithLogitsLoss(reduction="mean")
        self.assertEqual(0, losses.risk_loss.ndim)
        self.assertEqual(0, losses.type_loss.ndim)
        self.assertEqual(0, losses.total_loss.ndim)
        torch.testing.assert_close(losses.risk_loss, criterion(logits.risk_logits, risk))
        torch.testing.assert_close(losses.type_loss, criterion(logits.type_logits, types))
        torch.testing.assert_close(losses.total_loss, losses.risk_loss + losses.type_loss)
        self.assertLess(losses.risk_loss.item(), 0.2)  # sigmoid-first loss would differ.
        weighted = compute_losses(logits, risk, types, lambda_risk=2.0, lambda_type=0.5)
        torch.testing.assert_close(weighted.total_loss,
                                   2.0 * weighted.risk_loss + 0.5 * weighted.type_loss)

    def test_loss_shape_and_dtype_validation(self):
        logits = ModelOutput(torch.zeros((2, 1)), torch.zeros((2, 8)))
        with self.assertRaises(ValueError):
            compute_losses(logits, torch.zeros(2), torch.zeros((2, 8)))
        with self.assertRaises(ValueError):
            compute_losses(logits, torch.zeros((2, 1)), torch.zeros((2, 7)))
        with self.assertRaises(TypeError):
            compute_losses(logits, torch.zeros((2, 1), dtype=torch.int64), torch.zeros((2, 8)))

    def test_each_loss_reaches_its_head_and_shared_encoder(self):
        model = tiny_model()
        ids = torch.tensor([[2, 4, 3, 5, 3]])
        output = model(ids, torch.ones_like(ids), torch.tensor([[0, 0, 0, 1, 1]]))
        losses = compute_losses(output, torch.ones((1, 1)), torch.ones((1, 8)))
        encoder_parameter = model.encoder.embeddings.word_embeddings.weight
        risk_gradients = torch.autograd.grad(
            losses.risk_loss, (encoder_parameter, model.risk_classifier.weight),
            retain_graph=True,
        )
        type_gradients = torch.autograd.grad(
            losses.type_loss, (encoder_parameter, model.type_classifier.weight),
            retain_graph=True,
        )
        self.assertTrue(all(torch.isfinite(grad).all() and grad.abs().sum() > 0
                            for grad in risk_gradients + type_gradients))
        losses.total_loss.backward()
        self.assertTrue(all(parameter.grad is not None for parameter in model.parameters()))


class TrainingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.addClassCleanup(torch.set_num_threads, torch.get_num_threads())
        torch.set_num_threads(1)

    def test_config_and_seed_validation(self):
        for override in ({"data_version": ""}, {"batch_size": 0}, {"epochs": 0},
                         {"learning_rate": 0}, {"lambda_risk": 0, "lambda_type": 0},
                         {"weight_decay": -1}, {"seed": -1}):
            with self.subTest(override=override), self.assertRaises(ValueError):
                TrainingConfig(**dict({"data_version": "synthetic-v1"}, **override))
        set_training_seed(17)
        first = (random.random(), torch.rand(1).item())
        set_training_seed(17)
        self.assertEqual(first, (random.random(), torch.rand(1).item()))

    def test_model_factory_seeds_random_heads_before_initialization(self):
        config = TrainingConfig(data_version="synthetic-v1", seed=17)
        with patch("risk_speech_ai.training.RiskSpeechClassifier", side_effect=tiny_model):
            first = create_training_model(config)
            second = create_training_model(config)
        for key, tensor in first.state_dict().items():
            torch.testing.assert_close(tensor, second.state_dict()[key])

    def test_synthetic_train_all_samples_and_checkpoint_round_trip(self):
        tokenizer = SmallPairTokenizer()
        samples = [
            TrainingSample("P0001", 1, [], "short", 0.0, [0] * 8),
            TrainingSample("P0001", 2, ["short"], "send money now", 1.0,
                           [0, 1, 0, 0, 0, 0, 0, 0]),
            TrainingSample("P0001", 3, ["short", "send money now"], "okay", 0.0, [0] * 8),
        ]
        config = TrainingConfig(data_version="synthetic-v1", batch_size=2, epochs=2,
                                learning_rate=1e-3, model_revision="fixture-model",
                                tokenizer_revision="fixture-tokenizer")
        model = tiny_model()
        before = model.risk_classifier.weight.detach().clone()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "last.pt"
            result = train_model(model, samples, tokenizer, config,
                                 checkpoint_path=path, device="cpu")
            self.assertEqual(3, result.sample_count)
            self.assertEqual(4, result.step_count)
            self.assertEqual(2, len(result.epoch_losses))
            self.assertTrue(all(math.isfinite(item.average_total_loss) and
                                math.isfinite(item.average_risk_loss) and
                                math.isfinite(item.average_type_loss)
                                for item in result.epoch_losses))
            self.assertFalse(torch.equal(before, model.risk_classifier.weight))
            self.assertTrue(path.is_file())
            restored = tiny_model()
            optimizer = torch.optim.AdamW(restored.parameters(), lr=config.learning_rate)
            checkpoint = load_training_checkpoint(path, restored, tokenizer=tokenizer, optimizer=optimizer)
            self.assertEqual(2, checkpoint["epoch"])
            self.assertEqual("last_epoch", checkpoint["metadata"]["checkpoint_rule"])
            self.assertEqual("all_eligible_samples", checkpoint["metadata"]["training_split"])
            self.assertEqual(list(LABELS), checkpoint["label_order"])
            self.assertEqual(BASE_MODEL_NAME, checkpoint["base_model"])
            self.assertEqual("fixture-model", checkpoint["metadata"]["model_revision"])
            self.assertEqual("fixture-tokenizer", checkpoint["metadata"]["tokenizer_revision"])
            self.assertEqual("fixture-model", checkpoint["metadata"]["requested_model_revision"])
            self.assertIsNone(checkpoint["metadata"]["resolved_model_revision"])
            self.assertEqual("fixture-tokenizer", checkpoint["metadata"]["requested_tokenizer_revision"])
            self.assertIsNone(checkpoint["metadata"]["resolved_tokenizer_revision"])
            self.assertEqual(5, checkpoint["metadata"]["input_contract"]["max_history_utterances"])
            self.assertEqual(512, checkpoint["metadata"]["input_contract"]["max_sequence_length"])
            self.assertEqual("right", checkpoint["metadata"]["tokenizer_metadata"]["padding_side"])
            self.assertEqual(2, checkpoint["metadata"]["encoder_config"]["num_attention_heads"])
            self.assertEqual("synthetic-v1", checkpoint["metadata"]["data_version"])
            self.assertEqual(config.seed, checkpoint["metadata"]["seed"])
            self.assertEqual(config.learning_rate, checkpoint["metadata"]["training_config"]["learning_rate"])
            self.assertEqual(config.batch_size, checkpoint["metadata"]["training_config"]["batch_size"])
            self.assertEqual(config.lambda_risk, checkpoint["metadata"]["training_config"]["lambda_risk"])
            self.assertEqual(config.lambda_type, checkpoint["metadata"]["training_config"]["lambda_type"])
            self.assertIsInstance(checkpoint["metadata"]["python_version"], str)
            self.assertIsInstance(checkpoint["metadata"]["torch_version"], str)
            self.assertIsInstance(checkpoint["metadata"]["transformers_version"], str)
            self.assertEqual(2, len(checkpoint["epoch_losses"]))
            self.assertTrue(optimizer.state)
            for key, value in model.state_dict().items():
                torch.testing.assert_close(value, restored.state_dict()[key])

    def test_empty_samples_and_frozen_model_fail_before_checkpoint(self):
        tokenizer = SmallPairTokenizer()
        config = TrainingConfig(data_version="synthetic-v1", epochs=1)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "unused.pt"
            with self.assertRaisesRegex(ValueError, "no eligible"):
                train_model(tiny_model(), [], tokenizer, config, checkpoint_path=path)
            model = tiny_model()
            model.encoder.embeddings.word_embeddings.weight.requires_grad_(False)
            with self.assertRaisesRegex(ValueError, "trainable"):
                train_model(model, [TrainingSample("P0001", 1, [], "x", 1.0,
                                                    [0, 1, 0, 0, 0, 0, 0, 0])],
                            tokenizer, config, checkpoint_path=path)
            self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
