"""Checkpoint identity and compatibility checks shared by training and inference."""

from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import torch

from .config import BASE_MODEL_NAME, MAX_HISTORY_UTTERANCES, MAX_SEQUENCE_LENGTH
from .labels import LABELS

INPUT_CONTRACT_VERSION = "v1"
CHECKPOINT_SCHEMA_VERSION = "v1"
TOKENIZER_PROBES = (
    "ABC XYZ",
    "금융감독원입니다.",
    "12345 test",
    "[MASK]",
)


class CheckpointCompatibilityError(ValueError):
    """A checkpoint cannot be restored under the supplied runtime contract."""


def input_contract() -> dict[str, Any]:
    return {
        "version": INPUT_CONTRACT_VERSION,
        "max_history_utterances": MAX_HISTORY_UTTERANCES,
        "max_sequence_length": MAX_SEQUENCE_LENGTH,
        "sequence_format": "[CLS] history [SEP] current [SEP]",
        "history_separator": "\n",
        "overflow_rule": "drop_oldest_whole_history_then_fail_current_only",
        "padding_side": "right",
    }


def tokenizer_metadata(tokenizer: Any) -> dict[str, Any]:
    """Record actual tokenizer attributes, including a vocabulary fingerprint."""

    vocabulary = tokenizer.get_vocab() if callable(getattr(tokenizer, "get_vocab", None)) else getattr(tokenizer, "vocab", None)
    if not isinstance(vocabulary, Mapping):
        raise ValueError("tokenizer must expose its vocabulary for checkpoint identity")
    serialized_vocab = json.dumps(dict(vocabulary), sort_keys=True, ensure_ascii=False).encode("utf-8")
    special_tokens = getattr(tokenizer, "special_tokens_map", {})
    if not isinstance(special_tokens, Mapping):
        raise ValueError("tokenizer special_tokens_map must be a mapping")
    return {
        "name": getattr(tokenizer, "name_or_path", None),
        "class_name": type(tokenizer).__module__ + "." + type(tokenizer).__qualname__,
        "vocab_size": getattr(tokenizer, "vocab_size", len(vocabulary)),
        "vocab_sha256": hashlib.sha256(serialized_vocab).hexdigest(),
        "model_max_length": getattr(tokenizer, "model_max_length", None),
        "padding_side": getattr(tokenizer, "padding_side", None),
        "special_tokens_map": json.loads(json.dumps(dict(special_tokens), ensure_ascii=False)),
        "cls_token_id": getattr(tokenizer, "cls_token_id", None),
        "sep_token_id": getattr(tokenizer, "sep_token_id", None),
        "pad_token_id": getattr(tokenizer, "pad_token_id", None),
        "resolved_revision": getattr(tokenizer, "init_kwargs", {}).get("_commit_hash"),
    }


def tokenizer_behavior(tokenizer: Any) -> list[dict[str, Any]]:
    """Capture actual sentence-pair encoding for fixed, versioned probes."""

    from .tokenization import build_model_input

    return [
        {
            "text": probe,
            "input_ids": prepared.input_ids,
            "attention_mask": prepared.attention_mask,
            "token_type_ids": prepared.token_type_ids,
        }
        for probe in TOKENIZER_PROBES
        for prepared in [build_model_input([], probe, tokenizer=tokenizer)]
    ]


def encoder_config(model: Any) -> dict[str, Any]:
    """Store the encoder configuration, excluding its local load path and revision."""

    config = model.encoder.config
    result = json.loads(config.to_json_string(use_diff=False))
    result.pop("_name_or_path", None)
    result.pop("_commit_hash", None)
    return result


def read_checkpoint(path: str | Path, *, map_location: str | torch.device = "cpu") -> dict[str, Any]:
    checkpoint = torch.load(path, map_location=map_location, weights_only=True)
    if not isinstance(checkpoint, dict):
        raise CheckpointCompatibilityError("checkpoint must be a dictionary")
    return checkpoint


def _required(mapping: Mapping[str, Any], names: tuple[str, ...], location: str) -> None:
    missing = [name for name in names if name not in mapping]
    if missing:
        raise CheckpointCompatibilityError(f"{location} missing required fields: {', '.join(missing)}")


def validate_checkpoint_metadata(checkpoint: Mapping[str, Any]) -> Mapping[str, Any]:
    _required(checkpoint, (
        "checkpoint_schema_version", "label_order", "base_model", "training_config",
        "model_state_dict", "optimizer_state_dict", "metadata",
    ), "checkpoint")
    if type(checkpoint["checkpoint_schema_version"]) is not str or checkpoint["checkpoint_schema_version"] != CHECKPOINT_SCHEMA_VERSION:
        raise CheckpointCompatibilityError("unsupported checkpoint schema version")
    if not isinstance(checkpoint["label_order"], list):
        raise CheckpointCompatibilityError("checkpoint label order must be a list")
    if checkpoint.get("label_order") != list(LABELS):
        raise CheckpointCompatibilityError("checkpoint label order does not match canonical labels")
    if checkpoint.get("base_model") != BASE_MODEL_NAME:
        raise CheckpointCompatibilityError("checkpoint base model does not match configuration")
    metadata = checkpoint.get("metadata")
    if not isinstance(metadata, Mapping):
        raise CheckpointCompatibilityError("checkpoint metadata is missing")
    _required(metadata, (
        "checkpoint_schema_version", "model_name", "base_model", "label_order",
        "training_config", "data_version", "seed", "requested_revision",
        "resolved_revision", "requested_model_revision", "resolved_model_revision",
        "requested_tokenizer_revision", "resolved_tokenizer_revision",
        "model_revision", "tokenizer_revision", "tokenizer_metadata",
        "tokenizer_behavior", "encoder_config", "input_contract",
    ), "metadata")
    if type(metadata["checkpoint_schema_version"]) is not str or metadata["checkpoint_schema_version"] != CHECKPOINT_SCHEMA_VERSION:
        raise CheckpointCompatibilityError("unsupported metadata schema version")
    if metadata["model_name"] != BASE_MODEL_NAME or metadata["base_model"] != BASE_MODEL_NAME:
        raise CheckpointCompatibilityError("checkpoint metadata does not match the model contract")
    if not isinstance(metadata["label_order"], list) or metadata["label_order"] != list(LABELS):
        raise CheckpointCompatibilityError("checkpoint metadata label order does not match canonical labels")
    if not isinstance(checkpoint["training_config"], dict) or not isinstance(metadata["training_config"], dict):
        raise CheckpointCompatibilityError("training_config must be a dictionary")
    if checkpoint["training_config"] != metadata["training_config"]:
        raise CheckpointCompatibilityError("checkpoint training_config differs from metadata")
    if type(metadata["seed"]) is not int or metadata["seed"] < 0:
        raise CheckpointCompatibilityError("metadata seed must be a non-negative integer")
    if not isinstance(metadata["data_version"], str) or not metadata["data_version"].strip():
        raise CheckpointCompatibilityError("metadata data_version must be a non-empty string")
    config = metadata["training_config"]
    _required(config, ("data_version", "seed", "learning_rate", "batch_size", "epochs",
                       "lambda_risk", "lambda_type", "weight_decay", "model_revision",
                       "tokenizer_revision"), "training_config")
    if config["data_version"] != metadata["data_version"] or config["seed"] != metadata["seed"]:
        raise CheckpointCompatibilityError("training_config differs from metadata data_version or seed")
    for name in ("requested_revision", "resolved_revision", "requested_model_revision",
                 "resolved_model_revision", "requested_tokenizer_revision", "resolved_tokenizer_revision",
                 "model_revision", "tokenizer_revision"):
        value = metadata[name]
        if value is not None and (not isinstance(value, str) or not value.strip()):
            raise CheckpointCompatibilityError(f"metadata {name} must be a string or None")
    if (metadata["requested_revision"] != metadata["requested_model_revision"]
            or metadata["resolved_revision"] != metadata["resolved_model_revision"]
            or config["model_revision"] != metadata["requested_model_revision"]
            or config["tokenizer_revision"] != metadata["requested_tokenizer_revision"]):
        raise CheckpointCompatibilityError("checkpoint revision fields disagree")
    if metadata["model_revision"] != (metadata["resolved_model_revision"] or metadata["requested_model_revision"]):
        raise CheckpointCompatibilityError("checkpoint model revision fields disagree")
    if metadata["tokenizer_revision"] != (metadata["resolved_tokenizer_revision"] or metadata["requested_tokenizer_revision"]):
        raise CheckpointCompatibilityError("checkpoint tokenizer revision fields disagree")
    if not isinstance(metadata["tokenizer_metadata"], dict) or not isinstance(metadata["tokenizer_behavior"], list):
        raise CheckpointCompatibilityError("checkpoint tokenizer metadata or behavior has invalid type")
    if len(metadata["tokenizer_behavior"]) != len(TOKENIZER_PROBES):
        raise CheckpointCompatibilityError("checkpoint tokenizer behavior has invalid probe count")
    for probe, result in zip(TOKENIZER_PROBES, metadata["tokenizer_behavior"]):
        if (not isinstance(result, dict) or result.get("text") != probe
                or any(not isinstance(result.get(field), list) or any(type(token) is not int for token in result[field])
                       for field in ("input_ids", "attention_mask", "token_type_ids"))):
            raise CheckpointCompatibilityError("checkpoint tokenizer behavior has invalid type")
    if metadata.get("input_contract") != input_contract():
        raise CheckpointCompatibilityError("checkpoint input contract does not match current preprocessing")
    if not isinstance(metadata.get("encoder_config"), dict):
        raise CheckpointCompatibilityError("checkpoint encoder config is missing")
    if not isinstance(checkpoint["model_state_dict"], Mapping) or not isinstance(checkpoint["optimizer_state_dict"], Mapping):
        raise CheckpointCompatibilityError("checkpoint state dictionaries have invalid type")
    return metadata


def validate_model_config(metadata: Mapping[str, Any], model: Any) -> None:
    if metadata["encoder_config"] != encoder_config(model):
        raise CheckpointCompatibilityError("checkpoint encoder config does not match loaded model")


def validate_tokenizer(metadata: Mapping[str, Any], tokenizer: Any) -> None:
    expected = metadata.get("tokenizer_metadata")
    behavior = tokenizer_behavior(tokenizer)
    actual = tokenizer_metadata(tokenizer)
    if actual["padding_side"] != "right":
        raise CheckpointCompatibilityError("tokenizer padding_side must be right for CLS pooling")
    if not isinstance(expected, dict) or expected != actual:
        raise CheckpointCompatibilityError("checkpoint tokenizer identity does not match loaded tokenizer")
    if metadata["tokenizer_behavior"] != behavior:
        raise CheckpointCompatibilityError("checkpoint tokenizer behavior does not match loaded tokenizer")


def load_training_checkpoint(
    path: str | Path, model: Any, *, tokenizer: Any,
    optimizer: torch.optim.Optimizer | None = None,
    map_location: str | torch.device = "cpu",
    checkpoint: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate every contract before changing model or optimizer state."""

    loaded = checkpoint if checkpoint is not None else read_checkpoint(path, map_location=map_location)
    metadata = validate_checkpoint_metadata(loaded)
    validate_model_config(metadata, model)
    validate_tokenizer(metadata, tokenizer)
    temporary_model = copy.deepcopy(model)
    try:
        temporary_model.load_state_dict(loaded["model_state_dict"])
    except (RuntimeError, ValueError, TypeError) as error:
        raise CheckpointCompatibilityError("checkpoint model state_dict is incompatible") from error
    model.load_state_dict(temporary_model.state_dict())
    if optimizer is not None:
        optimizer.load_state_dict(loaded["optimizer_state_dict"])
    return loaded
