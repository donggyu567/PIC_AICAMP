"""Real tokenizer and pretrained encoder inference smoke with synthetic text."""

import unittest

import torch

from risk_speech_ai.inference import InferenceInput, infer_batch
from risk_speech_ai.labels import LABELS
from risk_speech_ai.model import RiskSpeechClassifier
from risk_speech_ai.tokenization import build_model_input, load_koelectra_tokenizer


class KoElectraInferenceIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.addClassCleanup(torch.set_num_threads, torch.get_num_threads())
        torch.set_num_threads(1)

    def test_real_tokenizer_encoder_and_output_mapping(self):
        tokenizer = load_koelectra_tokenizer()
        model = RiskSpeechClassifier()
        item = InferenceInput(["금융감독원입니다."], "지금 안전계좌로 송금해주세요.")
        prepared = build_model_input(item.history_texts, item.current_text, tokenizer=tokenizer)
        results = infer_batch(model, [item], tokenizer=tokenizer, device="cpu")
        self.assertEqual(18, prepared.token_count)
        self.assertEqual(1, len(results))
        self.assertTrue(0 <= results[0].risk_score <= 100)
        self.assertEqual(list(LABELS), list(results[0].type_scores))
        self.assertEqual(list(LABELS), list(results[0].type_probabilities))
        self.assertTrue(set(results[0].detected_types).issubset(LABELS))
        self.assertFalse(model.training)


if __name__ == "__main__":
    unittest.main()
