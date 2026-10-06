"""Checkpoint compatibility failures must precede weight mutation."""

import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import torch
from transformers import ElectraConfig, ElectraModel

from risk_speech_ai.checkpoint import (
    CHECKPOINT_SCHEMA_VERSION, CheckpointCompatibilityError,
    INPUT_CONTRACT_VERSION, tokenizer_behavior, tokenizer_metadata,
)
from risk_speech_ai.config import BASE_MODEL_NAME
from risk_speech_ai.dataset import RiskSpeechDataset
from risk_speech_ai.inference import InferenceInput, infer_batch, load_checkpoint_inference
from risk_speech_ai.model import RiskSpeechClassifier
from risk_speech_ai.tokenization import TokenizerContractError, build_model_input
from risk_speech_ai.training import TrainingConfig, create_training_model, load_training_checkpoint, train_model
from risk_speech_ai.training_data import TrainingSample
from test_dataset import SmallPairTokenizer
from test_training import tiny_model


class CompatibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.addClassCleanup(torch.set_num_threads, torch.get_num_threads())
        torch.set_num_threads(1)
        cls.directory = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.directory.cleanup)
        cls.path = Path(cls.directory.name) / "last.pt"
        cls.tokenizer = SmallPairTokenizer()
        cls.sample = TrainingSample("S", 1, [], "send money", 1.0, [0, 1, 0, 0, 0, 0, 0, 0])
        cls.trained = tiny_model()
        train_model(cls.trained, [cls.sample], cls.tokenizer,
                    TrainingConfig(data_version="fixture", epochs=1, batch_size=1),
                    checkpoint_path=cls.path, device="cpu")

    def altered_checkpoint(self, mutate):
        checkpoint = copy.deepcopy(torch.load(self.path, weights_only=True))
        mutate(checkpoint)
        path = Path(self.directory.name) / (self.id().split(".")[-1] + ".pt")
        torch.save(checkpoint, path)
        return path

    def assert_weight_unchanged_after_failure(self, path, tokenizer, pattern, *, model=None):
        model = model if model is not None else tiny_model()
        before = {key: value.detach().clone() for key, value in model.state_dict().items()}
        with patch.object(model, "load_state_dict", wraps=model.load_state_dict) as restore:
            with self.assertRaisesRegex(ValueError, pattern):
                load_checkpoint_inference(path, tokenizer=tokenizer, model=model, device="cpu")
            restore.assert_not_called()
        for key, value in before.items():
            torch.testing.assert_close(value, model.state_dict()[key])

    def test_normal_restore_and_recorded_contract(self):
        session = load_checkpoint_inference(self.path, tokenizer=self.tokenizer,
                                            model=tiny_model(), device="cpu")
        self.assertEqual(INPUT_CONTRACT_VERSION,
                         session.training_metadata["input_contract"]["version"])
        self.assertEqual("initial-0.5", session.threshold_version)
        self.assertEqual(self.trained.encoder.config.num_attention_heads,
                         session.model.encoder.config.num_attention_heads)
        self.assertEqual(1, len(session.predict([InferenceInput([], "send money")])))
        checkpoint = torch.load(self.path, weights_only=True)
        self.assertEqual(CHECKPOINT_SCHEMA_VERSION, checkpoint["checkpoint_schema_version"])
        self.assertEqual(CHECKPOINT_SCHEMA_VERSION,
                         session.training_metadata["checkpoint_schema_version"])
        self.assertEqual(4, len(session.training_metadata["tokenizer_behavior"]))

    def test_real_tokenizer_behavior_change_is_rejected(self):
        from transformers import AutoTokenizer
        from risk_speech_ai.tokenization import load_koelectra_tokenizer

        original = load_koelectra_tokenizer()
        changed = AutoTokenizer.from_pretrained(
            BASE_MODEL_NAME, do_lower_case=not original.do_lower_case
        )
        self.assertEqual(tokenizer_metadata(original), tokenizer_metadata(changed))
        self.assertNotEqual(tokenizer_behavior(original), tokenizer_behavior(changed))
        path = self.altered_checkpoint(lambda cp: cp["metadata"].update({
            "tokenizer_metadata": tokenizer_metadata(original),
            "tokenizer_behavior": tokenizer_behavior(original),
        }))
        self.assert_weight_unchanged_after_failure(path, changed, "tokenizer behavior")
        load_checkpoint_inference(path, tokenizer=original, model=tiny_model(), device="cpu")

    def test_tokenizer_identity_mismatch_and_missing_revision_fail(self):
        for field, value in (("name", "different"), ("vocab_size", 999),
                             ("model_max_length", 128), ("special_tokens_map", {"cls_token": "X"}),
                             ("vocab_sha256", "wrong"), ("resolved_revision", "expected-hash")):
            with self.subTest(field=field):
                path = self.altered_checkpoint(
                    lambda cp: cp["metadata"]["tokenizer_metadata"].__setitem__(field, value)
                )
                self.assert_weight_unchanged_after_failure(path, self.tokenizer, "tokenizer identity")

    def test_tokenizer_mismatch_rejected_before_default_model_creation(self):
        path = self.altered_checkpoint(
            lambda cp: cp["metadata"]["tokenizer_metadata"].__setitem__("name", "different")
        )
        with patch("risk_speech_ai.inference.RiskSpeechClassifier") as factory:
            with self.assertRaisesRegex(ValueError, "tokenizer identity"):
                load_checkpoint_inference(path, tokenizer=self.tokenizer, device="cpu")
            factory.assert_not_called()

    def test_same_shape_different_attention_head_count_rejected(self):
        config = ElectraConfig(vocab_size=100, embedding_size=16, hidden_size=16,
                               num_hidden_layers=1, num_attention_heads=4,
                               intermediate_size=32, max_position_embeddings=512,
                               type_vocab_size=2)
        wrong = RiskSpeechClassifier(ElectraModel(config))
        self.assertEqual(tuple(self.trained.risk_classifier.weight.shape),
                         tuple(wrong.risk_classifier.weight.shape))
        self.assert_weight_unchanged_after_failure(self.path, self.tokenizer,
                                                   "encoder config", model=wrong)

    def test_bad_metadata_and_input_contract_fail_before_load(self):
        for field, value, pattern in (("base_model", "other", "model contract"),
                                      ("input_contract", {"version": "v0"}, "input contract")):
            with self.subTest(field=field):
                path = self.altered_checkpoint(
                    lambda cp: cp["metadata"].__setitem__(field, value)
                )
                self.assert_weight_unchanged_after_failure(path, self.tokenizer, pattern)

    def test_missing_metadata_fields_and_invalid_types_rejected(self):
        for field in ("training_config", "seed", "data_version", "requested_revision",
                      "resolved_revision", "requested_tokenizer_revision",
                      "resolved_tokenizer_revision", "tokenizer_behavior"):
            with self.subTest(field=field):
                path = self.altered_checkpoint(lambda cp: cp["metadata"].pop(field))
                self.assert_weight_unchanged_after_failure(path, self.tokenizer, "missing required")
        for field, value, pattern in (("seed", "42", "seed"),
                                      ("training_config", [], "training_config"),
                                      ("label_order", tuple(range(8)), "label order"),
                                      ("checkpoint_schema_version", 1, "schema version")):
            with self.subTest(field=field):
                path = self.altered_checkpoint(lambda cp: cp["metadata"].__setitem__(field, value))
                self.assert_weight_unchanged_after_failure(path, self.tokenizer, pattern)
        path = self.altered_checkpoint(lambda cp: cp.pop("training_config"))
        self.assert_weight_unchanged_after_failure(path, self.tokenizer, "missing required")

    def test_unknown_schema_version_is_rejected(self):
        for location in ("checkpoint", "metadata"):
            with self.subTest(location=location):
                path = self.altered_checkpoint(lambda cp: (
                    cp if location == "checkpoint" else cp["metadata"]
                ).__setitem__("checkpoint_schema_version", "v999"))
                self.assert_weight_unchanged_after_failure(path, self.tokenizer, "schema version")

    def test_corrupted_state_dict_keeps_target_weights(self):
        def corrupt(cp):
            cp["model_state_dict"]["risk_classifier.weight"].fill_(7)
            cp["model_state_dict"]["type_classifier.bias"] = torch.zeros(9)

        path = self.altered_checkpoint(corrupt)
        target = tiny_model()
        before = {key: value.clone() for key, value in target.state_dict().items()}
        with self.assertRaisesRegex(CheckpointCompatibilityError, "state_dict"):
            load_checkpoint_inference(path, tokenizer=self.tokenizer, model=target, device="cpu")
        for key, value in before.items():
            torch.testing.assert_close(value, target.state_dict()[key])

    def test_direct_restore_validates_before_model_and_optimizer(self):
        path = self.altered_checkpoint(
            lambda cp: cp["metadata"].__setitem__("base_model", "other")
        )
        model = tiny_model()
        optimizer = torch.optim.AdamW(model.parameters())
        before = model.risk_classifier.weight.detach().clone()
        with patch.object(model, "load_state_dict", wraps=model.load_state_dict) as restore:
            with self.assertRaisesRegex(ValueError, "model contract"):
                load_training_checkpoint(path, model, tokenizer=self.tokenizer, optimizer=optimizer)
            restore.assert_not_called()
        torch.testing.assert_close(before, model.risk_classifier.weight)
        self.assertFalse(optimizer.state)

    def test_revision_reaches_pretrained_loader(self):
        with patch("risk_speech_ai.model.ElectraModel.from_pretrained",
                   return_value=tiny_model().encoder) as load:
            create_training_model(TrainingConfig(data_version="fixture", model_revision="commit-123"))
        load.assert_called_once_with(BASE_MODEL_NAME, revision="commit-123")

    def test_left_padding_and_contradictory_target_rejected(self):
        tokenizer = SmallPairTokenizer()
        tokenizer.padding_side = "left"
        with self.assertRaisesRegex(TokenizerContractError, "padding_side"):
            build_model_input([], "send money", tokenizer=tokenizer)
        with self.assertRaisesRegex(TokenizerContractError, "padding_side"):
            RiskSpeechDataset([self.sample], tokenizer=tokenizer)
        with self.assertRaisesRegex(TokenizerContractError, "padding_side"):
            infer_batch(tiny_model(), [InferenceInput([], "send money")], tokenizer=tokenizer)
        with self.assertRaisesRegex(ValueError, "padding_side"):
            load_checkpoint_inference(self.path, tokenizer=tokenizer,
                                      model=tiny_model(), device="cpu")
        with self.assertRaisesRegex(ValueError, "normal risk_target"):
            RiskSpeechDataset([
                TrainingSample("S", 2, [], "normal", 0.0, [1] + [0] * 7)
            ], tokenizer=SmallPairTokenizer())
        RiskSpeechDataset([
            TrainingSample("S", 3, [], "out of taxonomy", 1.0, [0] * 8)
        ], tokenizer=SmallPairTokenizer())


if __name__ == "__main__":
    unittest.main()
