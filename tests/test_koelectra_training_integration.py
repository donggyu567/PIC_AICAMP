"""One synthetic optimizer step with the real cached KoELECTRA checkpoint."""

import unittest

import torch

from risk_speech_ai.dataset import RiskSpeechDataset, make_training_dataloader
from risk_speech_ai.model import RiskSpeechClassifier
from risk_speech_ai.tokenization import load_koelectra_tokenizer
from risk_speech_ai.training import compute_losses
from risk_speech_ai.training_data import TrainingSample


class KoElectraTrainingIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.addClassCleanup(torch.set_num_threads, torch.get_num_threads())
        torch.set_num_threads(1)

    def test_one_real_encoder_training_step_on_synthetic_text(self):
        tokenizer = load_koelectra_tokenizer()
        sample = TrainingSample(
            "SYNTHETIC", 1, ["금융감독원입니다."],
            "지금 안전계좌로 송금해주세요.", 1.0,
            [0, 1, 0, 0, 0, 0, 0, 0],
        )
        dataset = RiskSpeechDataset([sample], tokenizer=tokenizer)
        batch = next(iter(make_training_dataloader(
            dataset, tokenizer=tokenizer, batch_size=1, shuffle=False,
        )))
        self.assertEqual((1, len(dataset[0]["input_ids"])), tuple(batch["input_ids"].shape))
        model = RiskSpeechClassifier().train()
        optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4)
        before = model.risk_classifier.weight.detach().clone()
        optimizer.zero_grad()
        output = model(batch["input_ids"], batch["attention_mask"], batch["token_type_ids"])
        losses = compute_losses(output, batch["risk_target"], batch["type_targets"])
        self.assertTrue(torch.isfinite(losses.total_loss))
        losses.total_loss.backward()
        self.assertIsNotNone(model.encoder.embeddings.word_embeddings.weight.grad)
        self.assertIsNotNone(model.risk_classifier.weight.grad)
        self.assertIsNotNone(model.type_classifier.weight.grad)
        optimizer.step()
        self.assertFalse(torch.equal(before, model.risk_classifier.weight))


if __name__ == "__main__":
    unittest.main()
