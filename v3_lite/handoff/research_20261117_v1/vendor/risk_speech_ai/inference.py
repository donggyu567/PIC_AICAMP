"""Current-utterance inference from raw logits; no accumulated risk state."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any

import torch

from .checkpoint import read_checkpoint, validate_checkpoint_metadata, validate_tokenizer
from .labels import LABELS, NUM_LABELS
from .model import ModelOutput, RiskSpeechClassifier
from .tokenization import build_model_input
from .checkpoint import load_training_checkpoint


@dataclass(frozen=True)
class ThresholdConfig:
    """Versioned, independently configurable thresholds in canonical label order."""

    values: Mapping[str, float] = field(
        default_factory=lambda: {label: 0.5 for label in LABELS}
    )
    version: str = "initial-0.5"

    def __post_init__(self) -> None:
        if not isinstance(self.version, str) or not self.version.strip():
            raise ValueError("threshold version must be a non-empty string")
        if not isinstance(self.values, Mapping) or set(self.values) != set(LABELS):
            raise ValueError("thresholds must have exactly the canonical label keys")
        normalized = {}
        for label in LABELS:
            value = self.values[label]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"invalid threshold for {label}")
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"threshold for {label} must be between 0 and 1")
            normalized[label] = float(value)
        if self.version == "initial-0.5" and any(value != 0.5 for value in normalized.values()):
            raise ValueError("custom thresholds require a distinct version")
        object.__setattr__(self, "values", MappingProxyType(normalized))


@dataclass(frozen=True)
class InferenceInput:
    history_texts: Sequence[str]
    current_text: str


@dataclass(frozen=True)
class InferenceOutput:
    risk_score: float
    risk_probability: float
    type_scores: dict[str, float]
    type_probabilities: dict[str, float]
    detected_types: list[str]


def logits_to_outputs(
    output: ModelOutput, thresholds: ThresholdConfig | None = None,
) -> list[InferenceOutput]:
    """Convert a batch of raw logits without rounding before threshold checks."""

    config = thresholds if thresholds is not None else ThresholdConfig()
    risk = output.risk_logits
    types = output.type_logits
    if risk.ndim != 2 or risk.shape[0] == 0 or risk.shape[1] != 1:
        raise ValueError("risk_logits must have non-empty shape [B, 1]")
    if types.shape != (risk.shape[0], NUM_LABELS):
        raise ValueError(f"type_logits must have shape [B, {NUM_LABELS}]")
    if not torch.isfinite(risk).all() or not torch.isfinite(types).all():
        raise ValueError("logits must be finite")
    risk_probabilities = torch.sigmoid(risk.detach()).cpu().tolist()
    type_probabilities = torch.sigmoid(types.detach()).cpu().tolist()
    results = []
    for risk_row, type_row in zip(risk_probabilities, type_probabilities):
        probabilities = dict(zip(LABELS, type_row))
        results.append(InferenceOutput(
            risk_score=100.0 * risk_row[0],
            risk_probability=risk_row[0],
            type_scores={label: 100.0 * probabilities[label] for label in LABELS},
            type_probabilities=probabilities,
            detected_types=[label for label in LABELS
                            if probabilities[label] >= config.values[label]],
        ))
    return results


def infer_batch(
    model: RiskSpeechClassifier,
    inputs: Sequence[InferenceInput],
    *, tokenizer: Any,
    thresholds: ThresholdConfig | None = None,
    device: str | torch.device | None = None,
) -> list[InferenceOutput]:
    """Use the shared sentence-pair tokenizer and perform one batched forward."""

    if not inputs:
        return []
    features = []
    for item in inputs:
        if not isinstance(item, InferenceInput):
            raise TypeError("inputs must contain InferenceInput objects")
        prepared = build_model_input(item.history_texts, item.current_text, tokenizer=tokenizer)
        features.append({
            "input_ids": prepared.input_ids,
            "attention_mask": prepared.attention_mask,
            "token_type_ids": prepared.token_type_ids,
        })
    batch = tokenizer.pad(features, padding=True, return_tensors="pt")
    chosen_device = torch.device(device) if device is not None else next(model.parameters()).device
    model.to(chosen_device)
    model.eval()
    with torch.no_grad():
        output = model(
            input_ids=batch["input_ids"].to(chosen_device),
            attention_mask=batch["attention_mask"].to(chosen_device),
            token_type_ids=batch["token_type_ids"].to(chosen_device),
        )
    return logits_to_outputs(output, thresholds)


@dataclass
class CheckpointInference:
    model: RiskSpeechClassifier
    tokenizer: Any
    thresholds: ThresholdConfig
    training_metadata: dict[str, Any]
    device: torch.device
    threshold_version: str

    def predict(self, inputs: Sequence[InferenceInput]) -> list[InferenceOutput]:
        return infer_batch(
            self.model, inputs, tokenizer=self.tokenizer,
            thresholds=self.thresholds, device=self.device,
        )


def load_checkpoint_inference(
    checkpoint_path: str | Path,
    *, tokenizer: Any,
    thresholds: ThresholdConfig | None = None,
    device: str | torch.device | None = None,
    model: RiskSpeechClassifier | None = None,
) -> CheckpointInference:
    """Restore a Phase-5 checkpoint; keep threshold settings separate."""

    chosen_device = torch.device(device) if device is not None else torch.device(
        "cuda" if torch.cuda.is_available() else "cpu"
    )
    checkpoint = read_checkpoint(checkpoint_path)
    metadata = validate_checkpoint_metadata(checkpoint)
    if model is None:
        validate_tokenizer(metadata, tokenizer)
    revision = metadata.get("resolved_model_revision") or metadata.get("requested_model_revision")
    classifier = model if model is not None else RiskSpeechClassifier(
        **({"model_revision": revision} if revision is not None else {})
    )
    load_training_checkpoint(checkpoint_path, classifier, tokenizer=tokenizer, checkpoint=checkpoint)
    selected_thresholds = thresholds if thresholds is not None else ThresholdConfig()
    classifier.to(chosen_device)
    classifier.eval()
    return CheckpointInference(
        classifier, tokenizer, selected_thresholds,
        dict(metadata), chosen_device, selected_thresholds.version,
    )
