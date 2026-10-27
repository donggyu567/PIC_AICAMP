"""Read-only, in-sample diagnostics for the existing type classifier checkpoint."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np

from .inference import InferenceInput, load_checkpoint_inference
from .labels import LABELS
from .metrics import binary_metrics
from .tokenization import load_koelectra_tokenizer
from .train_cli import build_safe_training_samples, read_jsonl


EXPECTED_HASHES = {
    "checkpoint": "1131f9dcc665f79073d98ecd6845573109a89e44dbf2917d299a8fea057020a7",
    "labels": "c205049e1aa2125ad40cc6cea1465b2c2793cc7fedf02b7eab8e1d9f20e9c9e5",
    "tuned": "50ea88cc3ee9c3df1477082ab5daf82ef77f83329374b50f312874592462e6f2",
}
REVISION = "68b30cd259f34a4b5aa8786392612ba2a2617fcc"
EVALUATION_SET = "TRAIN (IN-SAMPLE)"


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def threshold_rows(targets: np.ndarray, probabilities: np.ndarray, label: str) -> list[dict]:
    rows = []
    for percent in range(5, 51):
        result = binary_metrics(targets, probabilities, percent / 100)
        rows.append({
            "evaluation_set": EVALUATION_SET, "label": label,
            "threshold": result["threshold"], "positive_predictions": result["tp"] + result["fp"],
            "tp": result["tp"], "fp": result["fp"], "fn": result["fn"],
            "precision": result["precision"], "recall": result["recall"], "f1": result["f1"],
        })
    return rows


def distribution_row(targets: np.ndarray, probabilities: np.ndarray, label: str) -> dict:
    result = binary_metrics(targets, probabilities)
    positive = probabilities[targets == 1]
    negative = probabilities[targets == 0]
    pooled_std = np.sqrt((float(np.var(positive)) + float(np.var(negative))) / 2)
    row = {
        "evaluation_set": EVALUATION_SET, "label": label,
        "positive": len(positive), "negative": len(negative),
        "prevalence": len(positive) / len(probabilities),
        "negative_to_positive_ratio": len(negative) / len(positive),
        "positive_mean": float(np.mean(positive)), "positive_median": float(np.median(positive)),
        "positive_max": float(np.max(positive)),
        "negative_mean": float(np.mean(negative)), "negative_median": float(np.median(negative)),
        "negative_max": float(np.max(negative)),
        "overall_min": float(np.min(probabilities)), "overall_max": float(np.max(probabilities)),
        "overall_std": float(np.std(probabilities)),
        "mean_gap_positive_minus_negative": float(np.mean(positive) - np.mean(negative)),
        "standardized_mean_gap": float((np.mean(positive) - np.mean(negative)) / pooled_std) if pooled_std else None,
        "roc_auc": result["roc_auc"], "average_precision": result["average_precision"],
    }
    for quantile in (50, 90, 95, 99):
        row[f"p{quantile}"] = float(np.percentile(probabilities, quantile))
    for threshold in (0.1, 0.2, 0.3, 0.4, 0.5):
        row[f"count_ge_{threshold:.1f}"] = int(np.count_nonzero(probabilities >= threshold))
    return row


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def svg_plots(output_dir: Path, sweep: list[dict], targets: np.ndarray, probabilities: np.ndarray) -> None:
    # Plain SVG avoids adding a plotting dependency to the training environment.
    from html import escape

    colors = ("#185abc", "#d93025", "#188038", "#9334e6", "#d56a00", "#008b8b", "#a14266", "#59636e")
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="1040" height="610" viewBox="0 0 1040 610">',
             '<rect width="1040" height="610" fill="white"/>',
             '<text x="65" y="30" font-size="19">F1 vs threshold — TRAIN (IN-SAMPLE)</text>',
             '<path d="M65 45 V505 H770" fill="none" stroke="#333"/>']
    for tick in range(6):
        y = 505 - tick * 90
        parts.append(f'<path d="M65 {y} H770" stroke="#e5e5e5"/>')
        parts.append(f'<text x="28" y="{y+4}" font-size="12">{tick/5:.1f}</text>')
    for j, label in enumerate(LABELS):
        points = [(65 + (row["threshold"] - .05) / .45 * 705, 505 - row["f1"] * 450)
                  for row in sweep if row["label"] == label]
        polyline = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
        parts.append(f'<polyline points="{polyline}" fill="none" stroke="{colors[j]}" stroke-width="2"/>')
        parts.append(f'<text x="790" y="{70+j*27}" fill="{colors[j]}" font-size="13">{escape(label)}</text>')
    for tick in (5, 10, 20, 30, 40, 50):
        x = 65 + (tick - 5) / 45 * 705
        parts.append(f'<text x="{x-12:.1f}" y="527" font-size="12">{tick/100:.2f}</text>')
    parts.append('<text x="350" y="560" font-size="14">Threshold (exploratory only)</text></svg>')
    (output_dir / "threshold_f1.svg").write_text("".join(parts), encoding="utf-8")

    # Eight faceted histograms; negative bars are scaled independently per facet.
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="1060" height="930" viewBox="0 0 1060 930">',
             '<rect width="1060" height="930" fill="white"/>',
             '<text x="30" y="28" font-size="19">Type probability distributions — TRAIN (IN-SAMPLE)</text>',
             '<text x="30" y="50" font-size="12">Blue: actual positive; orange: actual negative. Bars independently normalized within class.</text>']
    bins = np.linspace(0, .5, 26)
    for j, label in enumerate(LABELS):
        x0 = 35 + (j % 2) * 520
        y0 = 100 + (j // 2) * 205
        pos, _ = np.histogram(probabilities[targets[:, j] == 1, j], bins=bins)
        neg, _ = np.histogram(probabilities[targets[:, j] == 0, j], bins=bins)
        parts.append(f'<text x="{x0}" y="{y0-20}" font-size="14">{escape(label)} (P={int(sum(pos))}, N={int(sum(neg))})</text>')
        parts.append(f'<path d="M{x0} {y0+130} H{x0+470}" stroke="#333"/>')
        for k, (p, n) in enumerate(zip(pos, neg)):
            x = x0 + k * 18.5
            ph = p / max(pos.max(), 1) * 112
            nh = n / max(neg.max(), 1) * 112
            parts.append(f'<rect x="{x:.1f}" y="{y0+130-nh:.1f}" width="8" height="{nh:.1f}" fill="#d56a00" opacity=".7"/>')
            parts.append(f'<rect x="{x+8:.1f}" y="{y0+130-ph:.1f}" width="8" height="{ph:.1f}" fill="#185abc" opacity=".7"/>')
        parts.append(f'<text x="{x0}" y="{y0+147}" font-size="11">0.00</text><text x="{x0+425}" y="{y0+147}" font-size="11">0.50</text>')
    parts.append('</svg>')
    (output_dir / "probability_histograms.svg").write_text("".join(parts), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, default=Path("artifacts/risk_speech_ai/koelectra_risk_v1.pt"))
    parser.add_argument("--labels-jsonl", type=Path, default=Path("artifacts/risk_speech_ai/prepared/labels.jsonl"))
    parser.add_argument("--tuned-jsonl", type=Path, default=Path("artifacts/risk_speech_ai/prepared/tuned.jsonl"))
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/risk_speech_ai/reports/type_diagnostics"))
    parser.add_argument("--batch-size", type=int, default=8)
    args = parser.parse_args()
    if args.batch_size < 1:
        parser.error("batch-size must be positive")
    paths = {"checkpoint": args.checkpoint, "labels": args.labels_jsonl, "tuned": args.tuned_jsonl}
    for name, path in paths.items():
        actual = file_hash(path)
        if actual != EXPECTED_HASHES[name]:
            raise ValueError(f"{name} SHA-256 mismatch: {actual}")

    built, _ = build_safe_training_samples(read_jsonl(args.labels_jsonl), read_jsonl(args.tuned_jsonl))
    samples = built.samples
    if len(samples) != 1460:
        raise ValueError(f"expected 1460 samples, got {len(samples)}")
    targets = np.asarray([sample.type_targets for sample in samples], dtype=np.int8)
    tokenizer = load_koelectra_tokenizer(REVISION)
    session = load_checkpoint_inference(args.checkpoint, tokenizer=tokenizer, device="cpu")
    if tuple(session.training_metadata["label_order"]) != LABELS:
        raise ValueError("checkpoint label order mismatch")
    probabilities = np.empty((len(samples), len(LABELS)), dtype=np.float64)
    for start in range(0, len(samples), args.batch_size):
        chunk = samples[start:start + args.batch_size]
        predictions = session.predict([InferenceInput(sample.history_texts, sample.current_text) for sample in chunk])
        for offset, result in enumerate(predictions):
            probabilities[start + offset] = [result.type_probabilities[label] for label in LABELS]
        if (start // args.batch_size + 1) % 20 == 0 or start + len(chunk) == len(samples):
            print(f"inferred {start + len(chunk)}/{len(samples)}", flush=True)

    distribution = [distribution_row(targets[:, j], probabilities[:, j], label)
                    for j, label in enumerate(LABELS)]
    sweep = [row for j, label in enumerate(LABELS)
             for row in threshold_rows(targets[:, j], probabilities[:, j], label)]
    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    write_csv(output / "probability_distribution.csv", distribution)
    write_csv(output / "threshold_sweep.csv", sweep)
    svg_plots(output, sweep, targets, probabilities)
    best = {label: max((row for row in sweep if row["label"] == label),
                       key=lambda row: (row["f1"], row["threshold"])) for label in LABELS}
    summary = {"evaluation_set": EVALUATION_SET, "sample_count": len(samples), "input_sha256": EXPECTED_HASHES,
               "checkpoint_schema_version": "v1", "threshold_grid": "0.05..0.50 by 0.01",
               "best_thresholds_are_exploratory_only": True,
               "best_in_sample_threshold_by_label": best}
    (output / "diagnostic_metadata.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"distribution": distribution, "best": best}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
