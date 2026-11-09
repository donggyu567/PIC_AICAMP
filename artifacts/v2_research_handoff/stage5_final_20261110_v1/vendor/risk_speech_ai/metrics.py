"""Binary and multilabel evaluation without altering inference thresholds."""

from __future__ import annotations

import numpy as np

from .labels import LABELS


def _auc(y: np.ndarray, p: np.ndarray) -> float | None:
    positive = int(y.sum())
    negative = len(y) - positive
    if not positive or not negative:
        return None
    order = np.argsort(p, kind="stable")
    sorted_p = p[order]
    ranks = np.arange(1, len(y) + 1, dtype=float)
    _, starts, counts = np.unique(sorted_p, return_index=True, return_counts=True)
    for start, count in zip(starts, counts):
        ranks[start:start + count] = start + (count + 1) / 2
    positive_ranks = ranks[np.argsort(order)][y == 1].sum()
    return float((positive_ranks - positive * (positive + 1) / 2) / (positive * negative))


def _average_precision(y: np.ndarray, p: np.ndarray) -> float | None:
    positive = int(y.sum())
    if not positive:
        return None
    order = np.argsort(-p, kind="stable")
    sorted_y, sorted_p = y[order], p[order]
    total = 0.0
    tp = seen = 0
    start = 0
    while start < len(y):
        end = start + 1
        while end < len(y) and sorted_p[end] == sorted_p[start]:
            end += 1
        group_tp = int(sorted_y[start:end].sum())
        tp += group_tp
        seen = end
        total += group_tp / positive * (tp / seen)
        start = end
    return float(total)


def binary_metrics(targets: object, probabilities: object, threshold: float = 0.5) -> dict:
    y = np.asarray(targets)
    p = np.asarray(probabilities, dtype=float)
    if y.ndim != 1 or p.shape != y.shape or len(y) == 0:
        raise ValueError("targets and probabilities must be nonempty equal-length vectors")
    if not np.isin(y, [0, 1]).all() or not np.isfinite(p).all() or ((p < 0) | (p > 1)).any():
        raise ValueError("targets must be binary and probabilities finite in [0,1]")
    if not 0 <= threshold <= 1:
        raise ValueError("threshold must be in [0,1]")
    y = y.astype(int)
    predicted = (p >= threshold).astype(int)
    tp = int(((y == 1) & (predicted == 1)).sum())
    tn = int(((y == 0) & (predicted == 0)).sum())
    fp = int(((y == 0) & (predicted == 1)).sum())
    fn = int(((y == 1) & (predicted == 0)).sum())
    positive, negative = tp + fn, tn + fp
    precision = tp / (tp + fp) if tp + fp else (0.0 if positive else None)
    recall = tp / positive if positive else None
    f1 = (2 * tp / (2 * tp + fp + fn)) if positive else None
    result = {
        "n": len(y), "positive": positive, "negative": negative, "threshold": threshold,
        "tp": tp, "tn": tn, "fp": fp, "fn": fn,
        "confusion_matrix": [[tn, fp], [fn, tp]],
        "accuracy": (tp + tn) / len(y), "precision": precision, "recall": recall, "f1": f1,
        "roc_auc": _auc(y, p), "average_precision": _average_precision(y, p),
        "brier_score": float(np.mean((p - y) ** 2)),
        "probability": {"mean": float(np.mean(p)), "median": float(np.median(p)),
                        "std_population": float(np.std(p, ddof=0))},
        "probability_by_actual": {
            name: ({"n": int(mask.sum()), "mean": float(np.mean(p[mask])),
                    "median": float(np.median(p[mask])),
                    "std_population": float(np.std(p[mask], ddof=0)),
                    "min": float(np.min(p[mask])), "max": float(np.max(p[mask]))}
                   if mask.any() else None)
            for name, mask in (("positive", y == 1), ("negative", y == 0))
        },
        "undefined_reasons": {},
    }
    if not positive:
        result["undefined_reasons"].update({"recall": "no_actual_positive", "f1": "no_actual_positive",
                                             "average_precision": "no_actual_positive"})
    if not positive or not negative:
        result["undefined_reasons"]["roc_auc"] = "requires_positive_and_negative"
    if precision is None:
        result["undefined_reasons"]["precision"] = "no_predicted_or_actual_positive"
    return result


def multilabel_metrics(targets: object, probabilities: object, threshold: float = 0.5) -> dict:
    y = np.asarray(targets)
    p = np.asarray(probabilities, dtype=float)
    if y.ndim != 2 or y.shape[1] != len(LABELS) or p.shape != y.shape or len(y) == 0:
        raise ValueError("multilabel arrays must have nonempty shape [N, 8]")
    per_label = {name: binary_metrics(y[:, index], p[:, index], threshold)
                 for index, name in enumerate(LABELS)}
    counts = {key: sum(item[key] for item in per_label.values()) for key in ("tp", "tn", "fp", "fn")}
    micro_precision = counts["tp"] / (counts["tp"] + counts["fp"]) if counts["tp"] + counts["fp"] else 0.0
    micro_recall = counts["tp"] / (counts["tp"] + counts["fn"]) if counts["tp"] + counts["fn"] else None
    micro_f1 = 2 * counts["tp"] / (2 * counts["tp"] + counts["fp"] + counts["fn"]) if counts["tp"] + counts["fn"] else None
    def defined_mean(field: str) -> float | None:
        values = [item[field] for item in per_label.values() if item[field] is not None]
        return float(np.mean(values)) if values else None
    total_support = sum(item["positive"] for item in per_label.values())
    weighted_f1 = (sum(item["positive"] * item["f1"] for item in per_label.values()
                       if item["f1"] is not None) / total_support) if total_support else None
    return {
        "n": len(y), "threshold": threshold, "per_label": per_label,
        "micro": {"precision": micro_precision, "recall": micro_recall, "f1": micro_f1, **counts},
        "macro": {"precision": defined_mean("precision"), "recall": defined_mean("recall"),
                  "f1": defined_mean("f1"), "defined_f1_labels": sum(item["f1"] is not None for item in per_label.values())},
        "weighted_f1": weighted_f1,
        "hamming_loss": float(np.mean((p >= threshold) != y)),
        "exact_match_ratio": float(np.mean(np.all((p >= threshold) == y, axis=1))),
        "warnings": [f"{name}: only {item['positive']} positives; estimate is unstable"
                     for name, item in per_label.items() if item["positive"] < 10],
    }
