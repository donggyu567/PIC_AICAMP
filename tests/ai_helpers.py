"""Small tokenizer and randomly initialized model for offline AI tests."""

import torch
from transformers import ElectraConfig, ElectraModel

from risk_speech_ai.model import RiskSpeechClassifier


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


def tiny_model():
    config = ElectraConfig(vocab_size=100, embedding_size=16, hidden_size=16,
                           num_hidden_layers=1, num_attention_heads=2,
                           intermediate_size=32, max_position_embeddings=512,
                           type_vocab_size=2)
    return RiskSpeechClassifier(encoder=ElectraModel(config))
