"""TrainingSample tokenization and dynamic batch padding."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import torch
from torch.utils.data import DataLoader, Dataset

from .labels import NUM_LABELS
from .tokenization import TokenizerContractError, build_model_input
from .training_data import TrainingSample


class RiskSpeechDataset(Dataset):
    """Eagerly tokenize accepted samples; an overlong current fails before training."""

    def __init__(self, samples: Sequence[TrainingSample], *, tokenizer: Any) -> None:
        self.items: list[dict[str, Any]] = []
        for sample in samples:
            if not isinstance(sample, TrainingSample):
                raise TypeError("dataset requires TrainingSample objects")
            if sample.risk_target not in (0, 0.0, 1, 1.0):
                raise ValueError("risk_target must be 0 or 1")
            if len(sample.type_targets) != NUM_LABELS or any(
                target not in (0, 0.0, 1, 1.0) for target in sample.type_targets
            ):
                raise ValueError(f"type_targets must contain {NUM_LABELS} binary values")
            if sample.risk_target == 0 and any(sample.type_targets):
                raise ValueError("normal risk_target cannot have positive type_targets")
            prepared = build_model_input(sample.history_texts, sample.current_text, tokenizer=tokenizer)
            self.items.append({
                "input_ids": prepared.input_ids,
                "attention_mask": prepared.attention_mask,
                "token_type_ids": prepared.token_type_ids,
                "risk_target": float(sample.risk_target),
                "type_targets": [float(value) for value in sample.type_targets],
            })

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, index: int) -> dict[str, Any]:
        return self.items[index]


class DynamicPaddingCollator:
    def __init__(self, tokenizer: Any) -> None:
        if getattr(tokenizer, "padding_side", None) != "right":
            raise TokenizerContractError("tokenizer padding_side must be right for CLS pooling")
        self.tokenizer = tokenizer

    def __call__(self, items: list[dict[str, Any]]) -> dict[str, torch.Tensor]:
        if not items:
            raise ValueError("cannot collate an empty batch")
        features = [
            {key: item[key] for key in ("input_ids", "attention_mask", "token_type_ids")}
            for item in items
        ]
        batch = self.tokenizer.pad(features, padding=True, return_tensors="pt")
        return {
            "input_ids": batch["input_ids"],
            "attention_mask": batch["attention_mask"],
            "token_type_ids": batch["token_type_ids"],
            "risk_target": torch.tensor(
                [[item["risk_target"]] for item in items], dtype=torch.float32
            ),
            "type_targets": torch.tensor(
                [item["type_targets"] for item in items], dtype=torch.float32
            ),
        }


def make_training_dataloader(
    dataset: RiskSpeechDataset, *, tokenizer: Any, batch_size: int,
    shuffle: bool = True, seed: int = 42,
) -> DataLoader:
    if isinstance(batch_size, bool) or not isinstance(batch_size, int) or batch_size <= 0:
        raise ValueError("batch_size must be a positive integer")
    generator = torch.Generator().manual_seed(seed)
    return DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=shuffle,
        collate_fn=DynamicPaddingCollator(tokenizer),
        generator=generator,
        num_workers=0,
    )
