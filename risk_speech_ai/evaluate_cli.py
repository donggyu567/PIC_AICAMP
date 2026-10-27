"""Read-only in-sample evaluation and reproducibility report for a saved checkpoint."""

from __future__ import annotations

import argparse
import csv
import gc
import hashlib
import json
import platform
import statistics
import subprocess
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import torch
from transformers import __version__ as transformers_version

from .checkpoint import read_checkpoint, validate_checkpoint_metadata
from .config import CHECKPOINT_PATH
from .inference import InferenceInput, load_checkpoint_inference
from .labels import LABELS
from .metrics import binary_metrics, multilabel_metrics
from .tokenization import build_model_input, load_koelectra_tokenizer
from .train_cli import build_safe_training_samples, read_jsonl
from .training_log import working_set_bytes

EXPECTED_CHECKPOINT_SHA256 = "1131f9dcc665f79073d98ecd6845573109a89e44dbf2917d299a8fea057020a7"
DEFAULT_PREPARED = Path("artifacts/risk_speech_ai/prepared")
DEFAULT_REPORTS = Path("artifacts/risk_speech_ai/reports")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def _git(*args: str) -> str:
    result = subprocess.run(["git", *args], capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else "not_recorded"


def _duplicates(label_rows: list[dict], tuned_rows: list[dict]) -> dict:
    labels = {(row["conversation_id"], row["utterance_id"]): row for row in label_rows}
    by_text = defaultdict(list)
    for row in tuned_rows:
        by_text[row["tuned_text"]].append(labels[row["conversation_id"], row["utterance_id"]])
    repeated = [rows for rows in by_text.values() if len(rows) > 1]
    return {"identical_text_groups": len(repeated),
            "utterances_in_identical_text_groups": sum(map(len, repeated)),
            "same_conversation_groups": sum(len({row["conversation_id"] for row in rows}) == 1 for rows in repeated),
            "conflicting_risk_groups": sum(len({row["is_phishing"] for row in rows}) > 1 for rows in repeated),
            "conflicting_label_groups": sum(len({tuple(row["labels"]) for row in rows}) > 1 for rows in repeated),
            "duplicate_utterance_keys": len(label_rows) - len(labels)}


def _restore_history(report_dir: Path, checkpoint: dict, observation_path: Path) -> dict:
    observations = json.loads(observation_path.read_text(encoding="utf-8"))
    epoch_losses = checkpoint["epoch_losses"]
    path = report_dir / "training_history.csv"
    fields = ["record_type", "source", "epoch", "global_step", "cumulative_total_loss",
              "average_total_loss", "average_risk_loss", "average_type_loss",
              "batch_total_loss", "batch_risk_loss", "batch_type_loss", "batch_duration_ms",
              "epoch_duration_ms", "timestamp"]
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in observations["batch_cumulative"]:
            writer.writerow({"record_type": "cumulative_console", "source": observations["source"],
                             "epoch": row["epoch"], "global_step": row["global_step"],
                             "cumulative_total_loss": row["running_loss"],
                             **{field: "not_recorded" for field in fields[5:]}})
        for row in epoch_losses:
            writer.writerow({"record_type": "epoch_checkpoint", "source": "checkpoint_v1",
                             "epoch": row["epoch"], "global_step": checkpoint["step_count"],
                             "cumulative_total_loss": "not_recorded",
                             "average_total_loss": row["average_total_loss"],
                             "average_risk_loss": row["average_risk_loss"],
                             "average_type_loss": row["average_type_loss"],
                             **{field: "not_recorded" for field in fields[8:]}})
    return {"batch_cumulative_observations": observations["batch_cumulative"],
            "epoch_losses": epoch_losses,
            "batch_specific_losses": "not_recorded",
            "training_started_at": "not_recorded",
            "training_finished_at": "not_recorded",
            "training_duration_seconds": "not_recorded"}


def _latency_summary(values: list[float]) -> dict:
    return {"n": len(values), "mean_ms": statistics.mean(values),
            "median_ms": statistics.median(values),
            "p50_ms": float(np.percentile(values, 50)),
            "p95_ms": float(np.percentile(values, 95)),
            "min_ms": min(values), "max_ms": max(values)}


def _write_csv(path: Path, per_label: dict) -> None:
    fields = ["label", "positive", "negative", "tp", "tn", "fp", "fn", "precision",
              "recall", "f1", "roc_auc", "average_precision", "undefined_reasons"]
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for label in LABELS:
            item = per_label[label]
            writer.writerow({key: (json.dumps(item[key], ensure_ascii=False) if key == "undefined_reasons"
                                   else item[key]) for key in fields if key != "label"} | {"label": label})


def _svg_charts(report_dir: Path, metrics: dict, history: dict) -> None:
    # All chart inputs are aggregate numbers; no utterance text is included.
    points = [(row["global_step"], row["running_loss"])
              for row in history["batch_cumulative_observations"]]
    min_loss, max_loss = min(y for _, y in points), max(y for _, y in points)
    coords = " ".join(f"{50 + x / 183 * 550:.1f},{180 - (y - min_loss) / (max_loss - min_loss) * 130:.1f}"
                      for x, y in points)
    (report_dir / "loss_trend.svg").write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="650" height="220" viewBox="0 0 650 220">'
        f'<rect width="650" height="220" fill="white"/><text x="40" y="25" font-size="17">Recorded cumulative training loss</text>'
        f'<path d="M50 45 V180 H610" fill="none" stroke="#555"/><polyline points="{coords}" fill="none" stroke="#2468b4" stroke-width="3"/>'
        f'<text x="49" y="202" font-size="12">0</text><text x="575" y="202" font-size="12">183 steps</text>'
        f'<text x="8" y="55" font-size="12">{max_loss:.3f}</text><text x="8" y="180" font-size="12">{min_loss:.3f}</text></svg>', encoding="utf-8")
    confusion = metrics["risk"]["confusion_matrix"]
    cells = "".join(f'<rect x="{200 + c * 150}" y="{50 + r * 70}" width="145" height="65" fill="{["#d9efff", "#ffd9d9"][r != c]}"/>'
                    f'<text x="{260 + c * 150}" y="{90 + r * 70}" font-size="20">{confusion[r][c]}</text>'
                    for r in range(2) for c in range(2))
    (report_dir / "risk_confusion.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="560" height="230">'
        '<rect width="560" height="230" fill="white"/><text x="20" y="25" font-size="17">TRAIN (IN-SAMPLE) risk confusion</text>'
        '<text x="210" y="215" font-size="12">Predicted normal / phishing</text>'
        f'{cells}</svg>', encoding="utf-8")
    bars = "".join(f'<text x="5" y="{40 + i * 34}" font-size="12">{label}</text>'
                   f'<rect x="190" y="{25 + i * 34}" width="{max(1, 500 * (metrics["types"]["per_label"][label]["f1"] or 0)):.1f}" height="18" fill="#4682b4"/>'
                   f'<text x="{195 + 500 * (metrics["types"]["per_label"][label]["f1"] or 0):.1f}" y="{40 + i * 34}" font-size="12">{metrics["types"]["per_label"][label]["f1"] or 0:.3f}</text>'
                   for i, label in enumerate(LABELS))
    (report_dir / "per_label_f1.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="760" height="330">'
        '<rect width="760" height="330" fill="white"/><text x="5" y="18" font-size="17">TRAIN (IN-SAMPLE) per-label F1 at 0.5</text>'
        f'{bars}</svg>', encoding="utf-8")


def _markdown(metrics: dict, benchmark: dict, reproducibility: dict, history: dict) -> str:
    risk = metrics["risk"]
    types = metrics["types"]
    def fmt(value):
        return "N/A" if value is None else f"{value:.4f}"
    rows = [f"| {label} | {item['positive']} | {item['negative']} | {fmt(item['precision'])} | {fmt(item['recall'])} | {fmt(item['f1'])} | {fmt(item['roc_auc'])} | {fmt(item['average_precision'])} |"
            for label, item in types["per_label"].items()]
    return f"""# KoELECTRA v1 정량 평가

**평가 집합: TRAIN (IN-SAMPLE), {risk['n']}발화.** 모델이 학습한 발화를 다시 평가한 결과이며 독립 검증·테스트 성능이 아닙니다.

## 학습 기록

- 68개 대화, {risk['n']}발화; 피싱 {risk['positive']}, 정상 {risk['negative']}.
- 1 epoch, 183 optimizer steps, AdamW, batch size 8, learning rate 2e-5, weight decay 0.01, seed 42.
- 최종 평균 total/risk/type loss: {history['epoch_losses'][0]['average_total_loss']:.6f} / {history['epoch_losses'][0]['average_risk_loss']:.6f} / {history['epoch_losses'][0]['average_type_loss']:.6f}.
- 과거 20배치 간격 로그는 **해당 시점까지의 누적 평균 loss**다. 각 배치 자체의 loss와 정확한 학습 시작·종료 시각·소요 시간은 `not_recorded`다.

## 피싱 분류 · TRAIN (IN-SAMPLE), 임계값 0.5

Accuracy {fmt(risk['accuracy'])}, Precision {fmt(risk['precision'])}, Recall {fmt(risk['recall'])}, F1 {fmt(risk['f1'])}, ROC-AUC {fmt(risk['roc_auc'])}, Average Precision {fmt(risk['average_precision'])}, Brier {fmt(risk['brier_score'])}.

Confusion matrix `[[TN={risk['tn']}, FP={risk['fp']}], [FN={risk['fn']}, TP={risk['tp']}]]`.
전체 확률 평균/중앙값/모표준편차: {risk['probability']['mean']:.4f} / {risk['probability']['median']:.4f} / {risk['probability']['std_population']:.4f}. 양성 평균 {risk['probability_by_actual']['positive']['mean']:.4f}, 음성 평균 {risk['probability_by_actual']['negative']['mean']:.4f}.

## 위험 유형 · TRAIN (IN-SAMPLE), 각 임계값 0.5

| 유형 | 양성 | 음성 | Precision | Recall | F1 | ROC-AUC | AP |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
{chr(10).join(rows)}

Micro P/R/F1 {fmt(types['micro']['precision'])} / {fmt(types['micro']['recall'])} / {fmt(types['micro']['f1'])}; Macro P/R/F1 {fmt(types['macro']['precision'])} / {fmt(types['macro']['recall'])} / {fmt(types['macro']['f1'])}; Weighted F1 {fmt(types['weighted_f1'])}; Hamming loss {fmt(types['hamming_loss'])}; exact match {fmt(types['exact_match_ratio'])}.

`app_installation` 양성은 6개뿐이므로 추정치의 신뢰도가 낮다. 유형별 TP/TN/FP/FN과 정의 불가능한 지표의 사유는 `metrics.json` 및 `per_label_metrics.csv`에 있다.
기본 임계값에서 모든 유형의 TP와 FP가 0이다. 따라서 유형별 F1은 모두 0이며, 높은 exact match 비율은 주로 빈 라벨 발화를 모두 음성으로 맞춘 결과다. 유형별 AUC/AP는 순위 정보일 뿐 현재 임계값의 탐지 성공을 의미하지 않는다.

## CPU 추론 측정

- 모델 로딩 {benchmark['loading']['model_load_seconds']:.2f}초, 첫 단일 추론 {benchmark['cold_single_utterance_ms']:.2f}ms.
- 워밍업 3회 후 길이별 단일 발화 {benchmark['warm_single_utterance']['n']}회: 평균 {benchmark['warm_single_utterance']['mean_ms']:.2f}ms, p50 {benchmark['warm_single_utterance']['p50_ms']:.2f}ms, p95 {benchmark['warm_single_utterance']['p95_ms']:.2f}ms.
- 전체 평가 batch 8: {benchmark['full_train_evaluation']['utterances_per_second']:.2f}발화/초. 관측 working set {benchmark['observed_peak_working_set_bytes']} bytes ({benchmark['memory_measurement']}).
- 길이별 표본, 반복 횟수 및 측정 범위는 `inference_benchmark.json` 참조.

## 재현성 및 한계

- 데이터 버전 `{reproducibility['data_version']}`; Git 데이터 커밋 `{reproducibility['data_commit']}`.
- 체크포인트 SHA-256 `{reproducibility['checkpoint']['sha256']}`.
- 팀장 학습 사용 승인은 발화별 사람 검수 완료를 뜻하지 않는다. LLM 보정 없는 마스킹 텍스트를 사용했으므로 백엔드 실제 추론 입력과 차이가 있다.
- 제외 174발화. 상세 사유, 입력 파일 SHA-256, 중복 통계는 `reproducibility.json` 참조.
- 이 모델은 1 epoch 학습됐고 코드·체크포인트는 검증됐지만 **독립 데이터 일반화 성능은 검증되지 않았다**. 현재 1,460발화를 나중에 분할해도 독립 TEST가 되지 않는다.

![누적 loss](loss_trend.svg)

![피싱 혼동행렬](risk_confusion.svg)

![유형별 F1](per_label_f1.svg)
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, default=Path(CHECKPOINT_PATH))
    parser.add_argument("--prepared-dir", type=Path, default=DEFAULT_PREPARED)
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORTS)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--benchmark-repeats", type=int, default=8)
    args = parser.parse_args(argv)
    if args.batch_size <= 0 or args.benchmark_repeats <= 0:
        parser.error("batch size and benchmark repeats must be positive")
    if args.checkpoint.resolve() == Path(CHECKPOINT_PATH).resolve() and sha256_file(args.checkpoint) != EXPECTED_CHECKPOINT_SHA256:
        raise ValueError("canonical checkpoint hash differs from the trained v1 artifact")

    labels_path = args.prepared_dir / "labels.jsonl"
    tuned_path = args.prepared_dir / "tuned.jsonl"
    label_rows = read_jsonl(labels_path)
    tuned_rows = read_jsonl(tuned_path)
    built, build_statistics = build_safe_training_samples(label_rows, tuned_rows)
    if len(built.samples) != len(label_rows) or not built.samples:
        raise ValueError("evaluation inputs do not match the complete eligible training set")
    source_metadata = json.loads((args.prepared_dir / "provenance.json").read_text(encoding="utf-8"))
    checkpoint = read_checkpoint(args.checkpoint)
    metadata = dict(validate_checkpoint_metadata(checkpoint))
    if metadata["data_version"] != source_metadata["data_version"] or checkpoint["sample_count"] != len(built.samples):
        raise ValueError("checkpoint and prepared data version/sample count differ")
    args.report_dir.mkdir(parents=True, exist_ok=True)
    history = _restore_history(args.report_dir, checkpoint,
                               args.prepared_dir / "console_loss_observations_20261027.json")
    training_record = {"epoch": checkpoint["epoch"], "optimizer_steps": checkpoint["step_count"],
                       "optimizer": "AdamW", "training_config": checkpoint["training_config"],
                       "history": history}
    del checkpoint
    gc.collect()

    load_started = time.perf_counter()
    tokenizer = load_koelectra_tokenizer(metadata["tokenizer_revision"])
    tokenizer_load_seconds = time.perf_counter() - load_started
    model_started = time.perf_counter()
    session = load_checkpoint_inference(args.checkpoint, tokenizer=tokenizer, device="cpu")
    model_load_seconds = time.perf_counter() - model_started
    observed_memory = [value for value in (working_set_bytes(),) if value is not None]
    inputs = [InferenceInput(sample.history_texts, sample.current_text) for sample in built.samples]
    lengths = [build_model_input(item.history_texts, item.current_text, tokenizer=tokenizer).token_count
               for item in inputs]

    # Benchmark cold and warm single-item calls before the full batched evaluation.
    cold_started = time.perf_counter()
    first_index = int(np.argsort(lengths)[len(lengths) // 2])
    session.predict([inputs[first_index]])
    cold_ms = (time.perf_counter() - cold_started) * 1000
    for _ in range(3):
        session.predict([inputs[first_index]])

    actual_risk, predicted_risk, actual_types, predicted_types = [], [], [], []
    batch_latency: list[float] = []
    batch_length: list[int] = []
    evaluation_started = time.perf_counter()
    for offset in range(0, len(inputs), args.batch_size):
        group = inputs[offset:offset + args.batch_size]
        started = time.perf_counter()
        predictions = session.predict(group)
        batch_latency.append((time.perf_counter() - started) * 1000)
        batch_length.append(max(lengths[offset:offset + len(group)]))
        for sample, prediction in zip(built.samples[offset:offset + len(group)], predictions):
            actual_risk.append(int(sample.risk_target))
            predicted_risk.append(prediction.risk_probability)
            actual_types.append(sample.type_targets)
            predicted_types.append([prediction.type_probabilities[label] for label in LABELS])
        memory = working_set_bytes()
        if memory is not None:
            observed_memory.append(memory)
        if (offset // args.batch_size + 1) % 20 == 0 or offset + len(group) == len(inputs):
            print(f"evaluated={offset + len(group)}/{len(inputs)} batches={len(batch_latency)}", flush=True)
    evaluation_seconds = time.perf_counter() - evaluation_started
    risk = binary_metrics(actual_risk, predicted_risk)
    types = multilabel_metrics(actual_types, predicted_types)

    indices = [int(np.argmin(lengths)), int(np.argsort(lengths)[len(lengths) // 2]), int(np.argmax(lengths))]
    names = ("short", "medium", "long")
    warm_timings, by_length = [], {name: [] for name in names}
    for _ in range(args.benchmark_repeats):
        for name, index in zip(names, indices):
            start = time.perf_counter()
            session.predict([inputs[index]])
            elapsed = (time.perf_counter() - start) * 1000
            warm_timings.append(elapsed)
            by_length[name].append(elapsed)
            memory = working_set_bytes()
            if memory is not None:
                observed_memory.append(memory)
    benchmark = {
        "evaluation_set": "TRAIN (IN-SAMPLE)",
        "environment": {"device": "cpu", "python": platform.python_version(),
                        "torch": str(torch.__version__), "transformers": transformers_version,
                        "logical_cpus": __import__("os").cpu_count(), "torch_threads": torch.get_num_threads()},
        "loading": {"tokenizer_load_seconds": tokenizer_load_seconds,
                    "model_load_seconds": model_load_seconds,
                    "total_load_seconds": tokenizer_load_seconds + model_load_seconds},
        "cold_single_utterance_ms": cold_ms,
        "warmup": {"single_utterance_calls": 3, "token_length": lengths[first_index]},
        "warm_single_utterance": {**_latency_summary(warm_timings), "batch_size": 1,
                                  "repeats_per_length": args.benchmark_repeats,
                                  "utterances_per_second": 1000 / statistics.mean(warm_timings)},
        "by_token_length": {name: {"token_length": lengths[index], **_latency_summary(by_length[name])}
                            for name, index in zip(names, indices)},
        "full_train_evaluation": {"sample_count": len(inputs), "batch_size": args.batch_size,
                                  "batch_count": len(batch_latency), "wall_seconds": evaluation_seconds,
                                  "utterances_per_second": len(inputs) / evaluation_seconds,
                                  "batch_latency_ms": _latency_summary(batch_latency)},
        "batch_max_token_length_buckets": {
            name: _latency_summary([elapsed for elapsed, length in zip(batch_latency, batch_length) if lower < length <= upper])
            for name, lower, upper in (("1-128", 0, 128), ("129-256", 128, 256),
                                       ("257-384", 256, 384), ("385-512", 384, 512))
            if any(lower < length <= upper for length in batch_length)},
        "observed_peak_working_set_bytes": max(observed_memory) if observed_memory else None,
        "memory_measurement": "sampled current process working set, not guaranteed true peak",
    }
    metrics = {"evaluation_set": "TRAIN (IN-SAMPLE)", "threshold": 0.5,
               "sample_count": len(inputs), "actual_positive": sum(actual_risk),
               "actual_negative": len(inputs) - sum(actual_risk),
               "risk": risk, "types": types}
    reproducibility = {
        "evaluation_set": "TRAIN (IN-SAMPLE)", "checkpoint": {
            "path": str(args.checkpoint), "sha256": sha256_file(args.checkpoint),
            "bytes": args.checkpoint.stat().st_size, "schema_version": metadata["checkpoint_schema_version"]},
        "data_version": metadata["data_version"], "data_commit": source_metadata["data_commit"],
        "training_input_files": {"labels": {"path": str(labels_path), "sha256": sha256_file(labels_path)},
                                 "tuned": {"path": str(tuned_path), "sha256": sha256_file(tuned_path)}},
        "approval_policy": source_metadata["approval_policy"],
        "approval_basis": source_metadata["approval_basis"],
        "human_review_claimed": False,
        "preprocessing": source_metadata["preprocessing"],
        "backend_inference_preprocessing_difference": "backend may supply LLM-corrected tuned_text; training used validated masked source text without LLM correction",
        "excluded_utterances": source_metadata["excluded_utterances"],
        "excluded_by_reason": source_metadata["pending_reasons"],
        "conversation_count": len({row["conversation_id"] for row in label_rows}),
        "source_id_count": len({row["source"] for row in label_rows}),
        "duplicate_statistics": _duplicates(label_rows, tuned_rows),
        "builder_statistics": build_statistics,
        "label_order": list(LABELS),
        "model_name": metadata["base_model"],
        "requested_model_revision": metadata["requested_model_revision"],
        "resolved_model_revision": metadata["resolved_model_revision"],
        "requested_tokenizer_revision": metadata["requested_tokenizer_revision"],
        "resolved_tokenizer_revision": metadata["resolved_tokenizer_revision"],
        "tokenizer_vocab_sha256": metadata["tokenizer_metadata"]["vocab_sha256"],
        "training_environment": {"python": metadata["python_version"], "torch": metadata["torch_version"],
                                 "transformers": metadata["transformers_version"], "device": metadata["device"]},
        "current_code_commit": _git("rev-parse", "HEAD"),
        "current_worktree_dirty": bool(_git("status", "--porcelain")),
        "exact_uncommitted_training_code_snapshot": "not_recorded",
        "training": training_record,
        "independent_validation_available": False,
        "independent_test_available": False,
    }
    _write_json(args.report_dir / "metrics.json", metrics)
    _write_json(args.report_dir / "inference_benchmark.json", benchmark)
    _write_json(args.report_dir / "reproducibility.json", reproducibility)
    _write_csv(args.report_dir / "per_label_metrics.csv", types["per_label"])
    (args.report_dir / "metrics_report.md").write_text(
        _markdown(metrics, benchmark, reproducibility, history), encoding="utf-8")
    _svg_charts(args.report_dir, metrics, history)
    print(json.dumps({"evaluation_set": "TRAIN (IN-SAMPLE)", "samples": len(inputs),
                      "risk_accuracy": risk["accuracy"], "risk_f1": risk["f1"],
                      "type_macro_f1": types["macro"]["f1"],
                      "warm_mean_ms": benchmark["warm_single_utterance"]["mean_ms"],
                      "report_dir": str(args.report_dir)}, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
