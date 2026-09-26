"""Real checkpoint forward contract; run separately from fast unit tests."""

import unittest
from unittest.mock import patch

import torch
from transformers import ElectraModel

from risk_speech_ai.config import BASE_MODEL_NAME
from risk_speech_ai.checkpoint import encoder_config
from risk_speech_ai.labels import NUM_LABELS
from risk_speech_ai.model import RiskSpeechClassifier
from risk_speech_ai.tokenization import build_model_input, load_koelectra_tokenizer


class KoElectraModelIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.addClassCleanup(torch.set_num_threads, torch.get_num_threads())
        torch.set_num_threads(1)
        cls.tokenizer = load_koelectra_tokenizer()
        load_encoder = ElectraModel.from_pretrained

        def audited_load(*args, **kwargs):
            encoder, cls.loading_info = load_encoder(*args, output_loading_info=True, **kwargs)
            return encoder

        with patch.object(ElectraModel, "from_pretrained", side_effect=audited_load) as loader:
            cls.model = RiskSpeechClassifier().eval()
        loader.assert_called_once_with(BASE_MODEL_NAME)

    def test_pretrained_weights_and_parameter_counts(self):
        self.assertEqual([], self.loading_info["missing_keys"])
        self.assertEqual([], self.loading_info["mismatched_keys"])
        self.assertEqual([], self.loading_info["error_msgs"])
        self.assertTrue(all(
            name.startswith("discriminator_predictions.")
            for name in self.loading_info["unexpected_keys"]
        ))
        self.assertEqual(BASE_MODEL_NAME, self.model.encoder.config._name_or_path)
        self.assertEqual(112330752, sum(p.numel() for p in self.model.encoder.parameters()))
        self.assertEqual(769, sum(p.numel() for p in self.model.risk_classifier.parameters()))
        self.assertEqual(6152, sum(p.numel() for p in self.model.type_classifier.parameters()))
        self.assertEqual(112337673, sum(p.numel() for p in self.model.parameters()))
        self.assertEqual(112337673, sum(
            p.numel() for p in self.model.parameters() if p.requires_grad
        ))

    def test_real_encoder_configuration_is_recordable(self):
        recorded = encoder_config(self.model)
        self.assertEqual(768, recorded["hidden_size"])
        self.assertEqual(12, recorded["num_attention_heads"])
        self.assertEqual(self.model.encoder.config.num_hidden_layers,
                         recorded["num_hidden_layers"])

    def test_real_padded_batch_matches_individual_logits(self):
        prepared = [
            build_model_input([], "네.", tokenizer=self.tokenizer),
            build_model_input(["금융감독원입니다."], "지금 안전계좌로 송금해주세요.",
                              tokenizer=self.tokenizer),
        ]
        features = [
            {name: getattr(sample, name)
             for name in ("input_ids", "attention_mask", "token_type_ids")}
            for sample in prepared
        ]
        # Test fixture only; the production collator remains a later phase.
        batch = self.tokenizer.pad(features, padding=True, return_tensors="pt")
        self.assertTrue((batch["attention_mask"] == 0).any())
        self.assertTrue((batch["token_type_ids"] == 1).any())
        with torch.no_grad():
            outputs = self.model(**batch)
            for index, feature in enumerate(features):
                single = self.model(**{key: torch.tensor([value]) for key, value in feature.items()})
                torch.testing.assert_close(outputs.risk_logits[index:index + 1], single.risk_logits,
                                           atol=1e-5, rtol=1e-4)
                torch.testing.assert_close(outputs.type_logits[index:index + 1], single.type_logits,
                                           atol=1e-5, rtol=1e-4)
        self.assertEqual((2, 1), tuple(outputs.risk_logits.shape))
        self.assertEqual((2, NUM_LABELS), tuple(outputs.type_logits.shape))

    def test_real_tokenizer_to_encoder_and_two_heads(self):
        prepared = build_model_input(
            ["금융감독원입니다."],
            "지금 안전계좌로 송금해주세요.",
            tokenizer=self.tokenizer,
        )
        inputs = {
            "input_ids": torch.tensor([prepared.input_ids], dtype=torch.long),
            "attention_mask": torch.tensor([prepared.attention_mask], dtype=torch.long),
            "token_type_ids": torch.tensor([prepared.token_type_ids], dtype=torch.long),
        }
        with torch.no_grad():
            result = self.model(**inputs)
        self.assertEqual((1, prepared.token_count), tuple(inputs["input_ids"].shape))
        self.assertEqual((1, 1), tuple(result.risk_logits.shape))
        self.assertEqual((1, NUM_LABELS), tuple(result.type_logits.shape))
        self.assertTrue(torch.isfinite(result.risk_logits).all())
        self.assertTrue(torch.isfinite(result.type_logits).all())
        self.assertEqual(768, self.model.encoder.config.hidden_size)
        self.assertTrue(all(parameter.requires_grad for parameter in self.model.encoder.parameters()))


if __name__ == "__main__":
    unittest.main()
