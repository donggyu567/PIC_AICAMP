"""Shared KoELECTRA encoder with independent raw-logit risk and type heads."""

from __future__ import annotations

from dataclasses import dataclass

import torch
from torch import nn
from transformers import ElectraModel

from .config import BASE_MODEL_NAME, MAX_SEQUENCE_LENGTH
from .labels import NUM_LABELS


@dataclass(frozen=True)
class ModelOutput:
    risk_logits: torch.Tensor
    type_logits: torch.Tensor


class RiskSpeechClassifier(nn.Module):
    """Fine-tunable encoder; both heads read the same first-token state."""

    def __init__(self, encoder: ElectraModel | None = None, *, model_revision: str | None = None) -> None:
        super().__init__()
        if encoder is not None and model_revision is not None:
            raise ValueError("model_revision cannot be used with a supplied encoder")
        self.encoder = encoder if encoder is not None else ElectraModel.from_pretrained(
            BASE_MODEL_NAME, **({"revision": model_revision} if model_revision is not None else {})
        )
        hidden_size = self.encoder.config.hidden_size
        self.risk_classifier = nn.Linear(hidden_size, 1)
        self.type_classifier = nn.Linear(hidden_size, NUM_LABELS)

    def forward(
        self,
        input_ids: torch.Tensor,
        attention_mask: torch.Tensor,
        token_type_ids: torch.Tensor,
    ) -> ModelOutput:
        if input_ids.ndim != 2 or input_ids.shape[0] == 0:
            raise ValueError("input_ids must have non-empty batch shape [B, L]")
        if not 1 <= input_ids.shape[1] <= MAX_SEQUENCE_LENGTH:
            raise ValueError(f"sequence length must be between 1 and {MAX_SEQUENCE_LENGTH}")
        if attention_mask.shape != input_ids.shape or token_type_ids.shape != input_ids.shape:
            raise ValueError("attention_mask and token_type_ids must match input_ids shape [B, L]")
        encoded = self.encoder(
            input_ids=input_ids,
            attention_mask=attention_mask,
            token_type_ids=token_type_ids,
            return_dict=True,
        )
        cls_state = encoded.last_hidden_state[:, 0, :]
        return ModelOutput(
            risk_logits=self.risk_classifier(cls_state),
            type_logits=self.type_classifier(cls_state),
        )
