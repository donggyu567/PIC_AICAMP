"""Fast model contract tests using a tiny randomly initialized ELECTRA."""

import io
import unittest
from unittest.mock import patch

import torch
from transformers import ElectraConfig, ElectraModel

from risk_speech_ai.labels import NUM_LABELS
from risk_speech_ai.model import ModelOutput, RiskSpeechClassifier


def tiny_encoder():
    config = ElectraConfig(
        vocab_size=100,
        embedding_size=16,
        hidden_size=16,
        num_hidden_layers=1,
        num_attention_heads=2,
        intermediate_size=32,
        max_position_embeddings=512,
        type_vocab_size=2,
    )
    return ElectraModel(config)


class ModelStructureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.addClassCleanup(torch.set_num_threads, torch.get_num_threads())
        torch.set_num_threads(1)

    def test_encoder_receives_all_three_input_tensors_unchanged(self):
        model = RiskSpeechClassifier(encoder=tiny_encoder()).eval()
        ids = torch.tensor([[2, 4, 3, 5, 3, 0]])
        mask = torch.tensor([[1, 1, 1, 1, 1, 0]])
        segments = torch.tensor([[0, 0, 0, 1, 1, 0]])
        with patch.object(model.encoder, "forward", wraps=model.encoder.forward) as forward:
            model(ids, mask, segments)
        forward.assert_called_once()
        self.assertIs(ids, forward.call_args.kwargs["input_ids"])
        self.assertIs(mask, forward.call_args.kwargs["attention_mask"])
        self.assertIs(segments, forward.call_args.kwargs["token_type_ids"])

    def test_invalid_batch_shapes_and_lengths_fail_before_encoder(self):
        model = RiskSpeechClassifier(encoder=tiny_encoder())
        for ids, mask, segments in (
            (torch.ones(1, 513, dtype=torch.long),) * 3,
            (torch.ones(5, dtype=torch.long),) * 3,
            (torch.ones(0, 5, dtype=torch.long),) * 3,
            (torch.ones(1, 0, dtype=torch.long),) * 3,
            (torch.ones(2, 5, dtype=torch.long), torch.ones(1, 5), torch.zeros(2, 5)),
            (torch.ones(2, 5, dtype=torch.long), torch.ones(2, 5), torch.zeros(1, 5)),
        ):
            with self.subTest(shape=tuple(ids.shape), mask=tuple(mask.shape),
                              segments=tuple(segments.shape)):
                with patch.object(model.encoder, "forward") as encoder_forward:
                    with self.assertRaises(ValueError):
                        model(ids, mask, segments)
                    encoder_forward.assert_not_called()

    def test_encoder_and_two_linear_heads(self):
        model = RiskSpeechClassifier(encoder=tiny_encoder())
        self.assertIsInstance(model.encoder, ElectraModel)
        self.assertIsInstance(model.risk_classifier, torch.nn.Linear)
        self.assertIsInstance(model.type_classifier, torch.nn.Linear)
        self.assertEqual(model.encoder.config.hidden_size, model.risk_classifier.in_features)
        self.assertEqual(model.encoder.config.hidden_size, model.type_classifier.in_features)
        self.assertEqual(1, model.risk_classifier.out_features)
        self.assertEqual(NUM_LABELS, model.type_classifier.out_features)
        self.assertEqual(8, NUM_LABELS)
        self.assertTrue(all(parameter.requires_grad for parameter in model.encoder.parameters()))

    def test_batch_one_and_three_with_dynamic_lengths(self):
        model = RiskSpeechClassifier(encoder=tiny_encoder()).eval()
        with torch.no_grad():
            for batch, length in ((1, 22), (3, 128), (1, 512)):
                ids = torch.randint(0, 100, (batch, length))
                mask = torch.ones_like(ids)
                segments = torch.zeros_like(ids)
                outputs = model(ids, mask, segments)
                self.assertIsInstance(outputs, ModelOutput)
                self.assertEqual((batch, 1), tuple(outputs.risk_logits.shape))
                self.assertEqual((batch, NUM_LABELS), tuple(outputs.type_logits.shape))

    def test_both_heads_use_cls_and_return_unbounded_logits(self):
        class FixedEncoder(torch.nn.Module):
            def __init__(self):
                super().__init__()
                self.config = type("Config", (), {"hidden_size": 4})()
                self.scale = torch.nn.Parameter(torch.tensor(1.0))

            def forward(self, input_ids, attention_mask, token_type_ids, return_dict):
                states = torch.zeros((*input_ids.shape, 4))
                states[:, 0, 0] = 2.0 * self.scale
                states[:, 1:, 0] = 100.0 * self.scale
                return type("Output", (), {"last_hidden_state": states})()

        model = RiskSpeechClassifier(encoder=FixedEncoder())
        with torch.no_grad():
            model.risk_classifier.weight.zero_()
            model.risk_classifier.weight[0, 0] = 1.0
            model.risk_classifier.bias.zero_()
            model.type_classifier.weight.zero_()
            model.type_classifier.weight[:, 0] = -1.0
            model.type_classifier.bias.zero_()
        ids = torch.ones((3, 4), dtype=torch.long)
        output = model(ids, torch.ones_like(ids), torch.zeros_like(ids))
        self.assertTrue(torch.equal(torch.full((3, 1), 2.0), output.risk_logits))
        self.assertTrue(torch.equal(torch.full((3, NUM_LABELS), -2.0), output.type_logits))
        risk_gradient = torch.autograd.grad(
            output.risk_logits.sum(), model.encoder.scale, retain_graph=True
        )[0]
        type_gradient = torch.autograd.grad(output.type_logits.sum(), model.encoder.scale)[0]
        self.assertEqual(6.0, risk_gradient.item())
        self.assertEqual(-48.0, type_gradient.item())

    def test_standard_state_dict_round_trip(self):
        first = RiskSpeechClassifier(encoder=tiny_encoder())
        second = RiskSpeechClassifier(encoder=tiny_encoder())
        buffer = io.BytesIO()
        torch.save(first.state_dict(), buffer)
        buffer.seek(0)
        second.load_state_dict(torch.load(buffer, weights_only=True))
        for name, value in first.state_dict().items():
            self.assertTrue(torch.equal(value, second.state_dict()[name]), name)
        first.eval()
        second.eval()
        ids = torch.tensor([[2, 4, 3, 5, 3]])
        mask = torch.ones_like(ids)
        segments = torch.tensor([[0, 0, 0, 1, 1]])
        with torch.no_grad():
            original = first(ids, mask, segments)
            restored = second(ids, mask, segments)
        self.assertTrue(torch.equal(original.risk_logits, restored.risk_logits))
        self.assertTrue(torch.equal(original.type_logits, restored.type_logits))


if __name__ == "__main__":
    unittest.main()
