"""Validate reviewed JSONL inputs, then optionally train the canonical checkpoint."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .config import CHECKPOINT_PATH
from .tokenization import load_koelectra_tokenizer
from .training import TrainingConfig, create_training_model, train_model
from .training_data import build_training_samples


def read_jsonl(path: Path) -> list[Mapping[str, Any]]:
    rows = []
    with path.open(encoding="utf-8-sig") as source:
        for line_number, line in enumerate(source, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"{path}:{line_number}: invalid JSON") from error
            if not isinstance(row, dict):
                raise ValueError(f"{path}:{line_number}: expected a JSON object")
            rows.append(row)
    return rows


def build_safe_training_samples(
    label_rows: list[Mapping[str, Any]], tuned_rows: list[Mapping[str, Any]],
):
    """Keep excluded utterances out of both targets and history context."""
    initial = build_training_samples(label_rows, tuned_rows)
    eligible_keys = {(sample.conversation_id, sample.utterance_id) for sample in initial.samples}
    safe_tuned = [row for row in tuned_rows
                  if (row.get("conversation_id"), row.get("utterance_id")) in eligible_keys]
    return build_training_samples(label_rows, safe_tuned), initial.statistics


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--labels-jsonl", type=Path, required=True)
    parser.add_argument("--tuned-jsonl", type=Path, required=True)
    parser.add_argument("--data-version", required=True)
    parser.add_argument("--train", action="store_true", help="run fine-tuning and save the checkpoint")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--learning-rate", type=float, default=2e-5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--model-revision")
    parser.add_argument("--tokenizer-revision")
    parser.add_argument("--device", choices=("cpu", "cuda"))
    parser.add_argument("--log-dir", type=Path, help="base directory for a unique, durable training log")
    args = parser.parse_args(argv)

    config = TrainingConfig(
        data_version=args.data_version, epochs=args.epochs, batch_size=args.batch_size,
        learning_rate=args.learning_rate, seed=args.seed,
        model_revision=args.model_revision, tokenizer_revision=args.tokenizer_revision,
    )
    built, statistics = build_safe_training_samples(
        read_jsonl(args.labels_jsonl), read_jsonl(args.tuned_jsonl)
    )
    print(json.dumps(statistics, sort_keys=True))
    if not built.samples:
        raise ValueError("no eligible training samples")
    if not args.train:
        print("Validation only; no model was trained or checkpoint written.")
        return 0

    path = Path(CHECKPOINT_PATH)
    if path.exists():
        raise FileExistsError(f"checkpoint already exists: {path}")
    tokenizer = load_koelectra_tokenizer(config.tokenizer_revision)
    model = create_training_model(config)
    result = train_model(model, built.samples, tokenizer, config,
                         checkpoint_path=path, device=args.device, log_dir=args.log_dir)
    print(f"Saved {result.sample_count} trained samples after {result.step_count} steps: {result.checkpoint_path}")
    print(f"Training log: {result.journal_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
