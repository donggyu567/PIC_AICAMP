"""Train all eligible current-utterance samples and save the final epoch."""

from __future__ import annotations

import math
import platform
import random
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import torch
from torch import nn
from transformers import __version__ as transformers_version

from .checkpoint import (
    CHECKPOINT_SCHEMA_VERSION, encoder_config, input_contract,
    load_training_checkpoint, tokenizer_behavior, tokenizer_metadata,
)
from .config import BASE_MODEL_NAME
from .dataset import RiskSpeechDataset, make_training_dataloader
from .labels import LABELS, NUM_LABELS
from .model import ModelOutput, RiskSpeechClassifier
from .training_data import TrainingSample


@dataclass(frozen=True)
class TrainingConfig:
    data_version: str
    learning_rate: float = 2e-5
    batch_size: int = 8
    epochs: int = 3
    lambda_risk: float = 1.0
    lambda_type: float = 1.0
    seed: int = 42
    weight_decay: float = 0.01
    model_revision: str | None = None
    tokenizer_revision: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.data_version, str) or not self.data_version.strip():
            raise ValueError("data_version must be a non-empty identifier")
        for name in ("batch_size", "epochs"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int) or self.seed < 0:
            raise ValueError("seed must be a non-negative integer")
        for name in ("learning_rate", "weight_decay", "lambda_risk", "lambda_type"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"{name} must be finite")
            if value < 0 or (name == "learning_rate" and value == 0):
                raise ValueError(f"{name} must be positive or zero where allowed")
        if self.lambda_risk == self.lambda_type == 0:
            raise ValueError("at least one loss coefficient must be positive")
        for name in ("model_revision", "tokenizer_revision"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ValueError(f"{name} must be a non-empty string or None")


@dataclass(frozen=True)
class LossOutput:
    risk_loss: torch.Tensor
    type_loss: torch.Tensor
    total_loss: torch.Tensor


@dataclass(frozen=True)
class EpochLoss:
    epoch: int
    average_total_loss: float
    average_risk_loss: float
    average_type_loss: float


@dataclass(frozen=True)
class TrainingResult:
    epoch_losses: list[EpochLoss]
    sample_count: int
    step_count: int
    checkpoint_path: Path


def set_training_seed(seed: int) -> None:
    random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def create_training_model(config: TrainingConfig) -> RiskSpeechClassifier:
    """Seed before constructing the pretrained encoder and random task heads."""

    set_training_seed(config.seed)
    return RiskSpeechClassifier(**(
        {"model_revision": config.model_revision} if config.model_revision is not None else {}
    ))


def compute_losses(
    output: ModelOutput, risk_target: torch.Tensor, type_targets: torch.Tensor,
    *, lambda_risk: float = 1.0, lambda_type: float = 1.0,
) -> LossOutput:
    if output.risk_logits.ndim != 2 or output.risk_logits.shape[1] != 1:
        raise ValueError("risk_logits must have shape [B, 1]")
    if output.type_logits.shape != (output.risk_logits.shape[0], NUM_LABELS):
        raise ValueError(f"type_logits must have shape [B, {NUM_LABELS}]")
    if risk_target.shape != output.risk_logits.shape or type_targets.shape != output.type_logits.shape:
        raise ValueError("target shapes must exactly match logit shapes")
    if not risk_target.is_floating_point() or not type_targets.is_floating_point():
        raise TypeError("BCEWithLogitsLoss targets must be floating point")
    for coefficient in (lambda_risk, lambda_type):
        if not isinstance(coefficient, (int, float)) or not math.isfinite(coefficient) or coefficient < 0:
            raise ValueError("loss coefficients must be finite and non-negative")
    criterion = nn.BCEWithLogitsLoss(reduction="mean")
    risk_loss = criterion(output.risk_logits, risk_target)
    type_loss = criterion(output.type_logits, type_targets)
    return LossOutput(
        risk_loss=risk_loss,
        type_loss=type_loss,
        total_loss=lambda_risk * risk_loss + lambda_type * type_loss,
    )


def _metadata(model: RiskSpeechClassifier, tokenizer: Any, config: TrainingConfig, device: torch.device) -> dict[str, Any]:
    behavior = tokenizer_behavior(tokenizer)
    token_identity = tokenizer_metadata(tokenizer)
    resolved_model_revision = getattr(model.encoder.config, "_commit_hash", None)
    return {
        "checkpoint_schema_version": CHECKPOINT_SCHEMA_VERSION,
        "model_name": BASE_MODEL_NAME,
        "python_version": platform.python_version(),
        "torch_version": str(torch.__version__),
        "transformers_version": transformers_version,
        "base_model": BASE_MODEL_NAME,
        "model_revision": resolved_model_revision or config.model_revision,
        "tokenizer_revision": token_identity["resolved_revision"] or config.tokenizer_revision,
        "requested_model_revision": config.model_revision,
        "resolved_model_revision": resolved_model_revision,
        "requested_revision": config.model_revision,
        "resolved_revision": resolved_model_revision,
        "requested_tokenizer_revision": config.tokenizer_revision,
        "resolved_tokenizer_revision": token_identity["resolved_revision"],
        "tokenizer_metadata": token_identity,
        "tokenizer_behavior": behavior,
        "encoder_config": encoder_config(model),
        "input_contract": input_contract(),
        "label_order": list(LABELS),
        "data_version": config.data_version,
        "seed": config.seed,
        "training_config": asdict(config),
        "device": str(device),
        "training_split": "all_eligible_samples",
        "checkpoint_rule": "last_epoch",
    }


def train_model(
    model: RiskSpeechClassifier, samples: Sequence[TrainingSample], tokenizer: Any,
    config: TrainingConfig, *, checkpoint_path: str | Path, device: str | torch.device | None = None,
) -> TrainingResult:
    """Use every supplied eligible sample; create_training_model seeds new heads."""

    if not samples:
        raise ValueError("no eligible training samples")
    if any(not parameter.requires_grad for parameter in model.parameters()):
        raise ValueError("encoder and both heads must remain trainable")
    set_training_seed(config.seed)
    dataset = RiskSpeechDataset(samples, tokenizer=tokenizer)
    chosen_device = torch.device(device) if device is not None else torch.device(
        "cuda" if torch.cuda.is_available() else "cpu"
    )
    metadata = _metadata(model, tokenizer, config, chosen_device)
    loader = make_training_dataloader(
        dataset, tokenizer=tokenizer, batch_size=config.batch_size, shuffle=True,
        seed=config.seed,
    )
    model.to(chosen_device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=config.learning_rate,
                                  weight_decay=config.weight_decay)
    epoch_losses: list[EpochLoss] = []
    step_count = 0
    for epoch in range(1, config.epochs + 1):
        model.train()
        total_sum = risk_sum = type_sum = 0.0
        for batch in loader:
            batch = {key: value.to(chosen_device) for key, value in batch.items()}
            optimizer.zero_grad()
            output = model(
                input_ids=batch["input_ids"],
                attention_mask=batch["attention_mask"],
                token_type_ids=batch["token_type_ids"],
            )
            losses = compute_losses(
                output, batch["risk_target"], batch["type_targets"],
                lambda_risk=config.lambda_risk, lambda_type=config.lambda_type,
            )
            if not torch.isfinite(losses.total_loss):
                raise FloatingPointError("non-finite training loss")
            losses.total_loss.backward()
            optimizer.step()
            size = batch["input_ids"].shape[0]
            total_sum += losses.total_loss.detach().item() * size
            risk_sum += losses.risk_loss.detach().item() * size
            type_sum += losses.type_loss.detach().item() * size
            step_count += 1
        epoch_losses.append(EpochLoss(
            epoch=epoch,
            average_total_loss=total_sum / len(dataset),
            average_risk_loss=risk_sum / len(dataset),
            average_type_loss=type_sum / len(dataset),
        ))
    path = Path(checkpoint_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save({
        "checkpoint_schema_version": CHECKPOINT_SCHEMA_VERSION,
        "model_state_dict": model.state_dict(),
        "optimizer_state_dict": optimizer.state_dict(),
        "epoch": config.epochs,
        "training_config": asdict(config),
        "label_order": list(LABELS),
        "base_model": BASE_MODEL_NAME,
        "metadata": metadata,
        "epoch_losses": [asdict(item) for item in epoch_losses],
        "sample_count": len(dataset),
        "step_count": step_count,
    }, path)
    return TrainingResult(epoch_losses, len(dataset), step_count, path)
