"""Dataset, target, and batch padding contracts without network access."""

import unittest

import torch

from risk_speech_ai.dataset import RiskSpeechDataset, make_training_dataloader
from risk_speech_ai.tokenization import InputTooLongError
from risk_speech_ai.training_data import TrainingSample, build_training_samples


class SmallPairTokenizer:
    cls_token_id = 2
    sep_token_id = 3
    pad_token_id = 0
    padding_side = "right"

    def __init__(self):
        self.vocab = {}

    def __call__(self, text, *, text_pair, **kwargs):
        def ids(value):
            return [self.vocab.setdefault(word, len(self.vocab) + 4) for word in value.split()]

        first, second = ids(text), ids(text_pair)
        values = [2, *first, 3, *second, 3]
        return {
            "input_ids": values,
            "attention_mask": [1] * len(values),
            "token_type_ids": [0] * (len(first) + 2) + [1] * (len(second) + 1),
        }

    def pad(self, features, *, padding, return_tensors):
        assert padding is True and return_tensors == "pt"
        length = max(len(item["input_ids"]) for item in features)
        return {
            key: torch.tensor([
                item[key] + [0] * (length - len(item[key])) for item in features
            ], dtype=torch.long)
            for key in ("input_ids", "attention_mask", "token_type_ids")
        }


def sample(index, history, current, risk, types):
    return TrainingSample("P0001", index, history, current, risk, types)


class DatasetTests(unittest.TestCase):
    def test_eager_tokenization_and_dynamic_padding(self):
        tokenizer = SmallPairTokenizer()
        samples = [
            sample(1, [], "short", 0.0, [0] * 8),
            sample(2, ["longer history here"], "current has more words", 1.0,
                   [0, 1, 0, 0, 0, 0, 0, 0]),
        ]
        dataset = RiskSpeechDataset(samples, tokenizer=tokenizer)
        self.assertLess(len(dataset[0]["input_ids"]), len(dataset[1]["input_ids"]))
        batch = next(iter(make_training_dataloader(
            dataset, tokenizer=tokenizer, batch_size=2, shuffle=False,
        )))
        self.assertEqual((2, len(dataset[1]["input_ids"])), tuple(batch["input_ids"].shape))
        self.assertEqual(batch["input_ids"].shape, batch["attention_mask"].shape)
        self.assertEqual(batch["input_ids"].shape, batch["token_type_ids"].shape)
        self.assertEqual((2, 1), tuple(batch["risk_target"].shape))
        self.assertEqual((2, 8), tuple(batch["type_targets"].shape))
        self.assertEqual(torch.float32, batch["risk_target"].dtype)
        self.assertEqual(torch.float32, batch["type_targets"].dtype)
        self.assertTrue((batch["attention_mask"][0, len(dataset[0]["input_ids"]):] == 0).all())
        self.assertTrue((batch["token_type_ids"][0, len(dataset[0]["input_ids"]):] == 0).all())
        self.assertEqual(1.0, batch["risk_target"][1, 0].item())
        self.assertEqual(1.0, batch["type_targets"][1, 1].item())

    def test_all_and_only_eligible_samples_are_loaded(self):
        labels = [
            {"conversation_id": "P0001", "utterance_id": 1, "label_status": "reviewed",
             "is_phishing": False, "labels": []},
            {"conversation_id": "P0001", "utterance_id": 2, "label_status": "unreviewed",
             "is_phishing": True, "labels": []},
            {"conversation_id": "P0001", "utterance_id": 3, "label_status": "out_of_taxonomy",
             "is_phishing": True, "labels": []},
            {"conversation_id": "P0001", "utterance_id": 4,
             "is_phishing": True, "labels": ["money_transfer"]},
        ]
        tuned = [
            {"conversation_id": "P0001", "utterance_id": i, "tuned_text": f"utterance {i}"}
            for i in range(1, 5)
        ]
        built = build_training_samples(labels, tuned)
        self.assertEqual([1, 3], [item.utterance_id for item in built.samples])
        dataset = RiskSpeechDataset(built.samples, tokenizer=SmallPairTokenizer())
        self.assertEqual(2, len(dataset))
        self.assertEqual([0.0, 1.0], [item["risk_target"] for item in dataset])
        self.assertEqual([0.0] * 8, dataset[1]["type_targets"])
        self.assertEqual(["utterance 1", "utterance 2"], built.samples[1].history_texts)

    def test_overlong_current_fails_during_dataset_construction(self):
        tokenizer = SmallPairTokenizer()
        with self.assertRaises(InputTooLongError) as caught:
            RiskSpeechDataset([
                sample(1, ["history"], " ".join(["word"] * 510), 1.0, [0] * 8)
            ], tokenizer=tokenizer)
        self.assertEqual(513, caught.exception.token_count)
        self.assertEqual(1, caught.exception.dropped_history_count)

    def test_invalid_targets_and_batch_size_fail(self):
        tokenizer = SmallPairTokenizer()
        for invalid in (
            sample(1, [], "x", 0.5, [0] * 8),
            sample(1, [], "x", 0.0, [0] * 7),
            sample(1, [], "x", 0.0, [0] * 7 + [2]),
        ):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    RiskSpeechDataset([invalid], tokenizer=tokenizer)
        dataset = RiskSpeechDataset([sample(1, [], "x", 0.0, [0] * 8)], tokenizer=tokenizer)
        with self.assertRaises(ValueError):
            make_training_dataloader(dataset, tokenizer=tokenizer, batch_size=0)


if __name__ == "__main__":
    unittest.main()
