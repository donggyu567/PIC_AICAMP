"""Checkpoint startup contracts using only in-memory, tiny model fixtures."""

import copy
import unittest
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

import torch

from backend.services.ai_loader import load_risk_analyzer
from risk_speech_ai.checkpoint import CHECKPOINT_SCHEMA_VERSION, CheckpointCompatibilityError
from risk_speech_ai.config import BASE_MODEL_NAME
from risk_speech_ai.inference import load_checkpoint_inference
from risk_speech_ai.labels import LABELS
from risk_speech_ai.training import TrainingConfig, _metadata
from tests.ai_helpers import SmallPairTokenizer, tiny_model


class AiLoaderTests(unittest.TestCase):
    def setUp(self):
        self.source = tiny_model()
        self.tokenizer = SmallPairTokenizer()
        config = TrainingConfig(
            data_version="memory-fixture", model_revision="model-commit",
            tokenizer_revision="tokenizer-commit",
        )
        self.checkpoint = {
            "checkpoint_schema_version": CHECKPOINT_SCHEMA_VERSION,
            "model_state_dict": copy.deepcopy(self.source.state_dict()),
            "optimizer_state_dict": {},
            "training_config": asdict(config),
            "label_order": list(LABELS),
            "base_model": BASE_MODEL_NAME,
            "metadata": _metadata(self.source, self.tokenizer, config, torch.device("cpu")),
        }
        self.path = Path("unused-in-memory-checkpoint.pt")

    def test_server_reads_once_and_fresh_model_needs_no_copy(self):
        target = tiny_model()
        with (
            patch.object(Path, "is_file", return_value=True),
            patch("backend.services.ai_loader.read_checkpoint", return_value=self.checkpoint) as read,
            patch("backend.services.ai_loader.load_koelectra_tokenizer", return_value=self.tokenizer) as tokenizer,
            patch("risk_speech_ai.inference.read_checkpoint", side_effect=AssertionError("second read")),
            patch("risk_speech_ai.inference.RiskSpeechClassifier", return_value=target) as factory,
            patch("risk_speech_ai.checkpoint.copy") as copying,
        ):
            copying.deepcopy.side_effect = AssertionError("model copy")
            analyzer = load_risk_analyzer(self.path, model_version="trained-v1")
        read.assert_called_once_with(self.path.resolve())
        tokenizer.assert_called_once_with(revision="tokenizer-commit")
        factory.assert_called_once_with(model_revision="model-commit")
        self.assertEqual("trained-v1", analyzer.model_version)
        self.assertFalse(target.training)
        for key, value in self.source.state_dict().items():
            torch.testing.assert_close(value, target.state_dict()[key])

    def test_standalone_loader_still_reads_when_data_not_supplied(self):
        with patch("risk_speech_ai.inference.read_checkpoint", return_value=self.checkpoint) as read:
            session = load_checkpoint_inference(
                self.path, tokenizer=self.tokenizer, model=tiny_model(), device="cpu",
            )
        read.assert_called_once_with(self.path)
        self.assertEqual("memory-fixture", session.training_metadata["data_version"])

    def test_preloaded_metadata_is_validated_before_model_creation(self):
        self.checkpoint["label_order"] = list(reversed(LABELS))
        with patch("risk_speech_ai.inference.RiskSpeechClassifier") as factory:
            with self.assertRaisesRegex(CheckpointCompatibilityError, "label order"):
                load_checkpoint_inference(
                    self.path, tokenizer=self.tokenizer, checkpoint=self.checkpoint, device="cpu",
                )
        factory.assert_not_called()

    def test_tokenizer_mismatch_fails_before_model_creation(self):
        self.checkpoint["metadata"]["tokenizer_metadata"]["vocab_sha256"] = "wrong"
        with patch("risk_speech_ai.inference.RiskSpeechClassifier") as factory:
            with self.assertRaisesRegex(CheckpointCompatibilityError, "tokenizer identity"):
                load_checkpoint_inference(
                    self.path, tokenizer=self.tokenizer, checkpoint=self.checkpoint, device="cpu",
                )
        factory.assert_not_called()

    def test_fresh_model_config_mismatch_fails_before_loading_weights(self):
        target = tiny_model()
        self.checkpoint["metadata"]["encoder_config"]["num_attention_heads"] = 4
        with (
            patch("risk_speech_ai.inference.RiskSpeechClassifier", return_value=target),
            patch.object(target, "load_state_dict", wraps=target.load_state_dict) as restore,
        ):
            with self.assertRaisesRegex(CheckpointCompatibilityError, "encoder config"):
                load_checkpoint_inference(
                    self.path, tokenizer=self.tokenizer, checkpoint=self.checkpoint, device="cpu",
                )
        restore.assert_not_called()

    def test_corrupt_fresh_model_state_is_reported_as_compatibility_error(self):
        self.checkpoint["model_state_dict"]["type_classifier.bias"] = torch.zeros(9)
        with patch("risk_speech_ai.inference.RiskSpeechClassifier", return_value=tiny_model()):
            with self.assertRaisesRegex(CheckpointCompatibilityError, "state_dict"):
                load_checkpoint_inference(
                    self.path, tokenizer=self.tokenizer, checkpoint=self.checkpoint, device="cpu",
                )

    def test_corrupt_state_does_not_mutate_caller_owned_model(self):
        target = tiny_model()
        before = copy.deepcopy(target.state_dict())
        self.checkpoint["model_state_dict"]["risk_classifier.weight"].fill_(7)
        self.checkpoint["model_state_dict"]["type_classifier.bias"] = torch.zeros(9)
        with self.assertRaisesRegex(CheckpointCompatibilityError, "state_dict"):
            load_checkpoint_inference(
                self.path, tokenizer=self.tokenizer, checkpoint=self.checkpoint,
                model=target, device="cpu",
            )
        for key, value in before.items():
            torch.testing.assert_close(value, target.state_dict()[key])


if __name__ == "__main__":
    unittest.main()
