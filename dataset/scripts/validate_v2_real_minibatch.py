#!/usr/bin/env python3
"""Validate real CPU DataLoader batches using pinned PR #35 code and tokenizer.

No training call, backward, optimizer or checkpoint write is performed. Optional
forward uses random weights in the real base architecture, never v1 weights.
"""
from __future__ import annotations

import argparse
import contextlib
import csv
import hashlib
import importlib.metadata
import io
import json
import os
import platform
import subprocess
import sys
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REFERENCE = ROOT / "artifacts/v1_reference/pr35_9bab7e383928"
CANDIDATE = ROOT / "dataset/04. processed/v2_pilot/training_candidate/pilot_single_review_train_candidate.jsonl"
REPORTS = ROOT / "reports/v2_pilot/ml_runtime"
REVISION = "68b30cd259f34a4b5aa8786392612ba2a2617fcc"
HF_HOME = ROOT / "artifacts/v2_runtime_assets/hf"
os.environ.update(HF_HOME=str(HF_HOME), HF_HUB_CACHE=str(HF_HOME / "hub"),
                  HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", HF_HUB_DISABLE_TELEMETRY="1")
sys.path.insert(0, str(REFERENCE))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--random-forward", action="store_true")
    args = parser.parse_args()
    REPORTS.mkdir(parents=True, exist_ok=True)
    protected = [ROOT / "dataset/04. processed/v2_pilot/pilot_canonical.jsonl", CANDIDATE,
                 ROOT / "dataset/review/v2_pilot/human_review.csv", ROOT / "dataset/review/v2_pilot/human_review_working.csv"]
    protected += sorted((ROOT / "dataset/04. processed/v2_pilot").glob("approval_*/*.jsonl"))
    manifest = json.loads((REFERENCE / "source_manifest.json").read_text(encoding="utf-8"))
    protected += [REFERENCE / entry["path"] for entry in manifest["files"]]
    before = {str(path.relative_to(ROOT)): sha(path) for path in protected}
    checks = []

    def check(name, passed, detail=None):
        checks.append({"name": name, "passed": bool(passed), "detail": detail})
        if not passed:
            raise AssertionError(name)

    report = {"status": "RUNNING", "checks": checks, "training_executed": False,
              "optimizer_steps": 0, "backward_calls": 0, "checkpoint_loaded": False, "checkpoint_written": False}
    try:
        import torch
        import transformers
        from risk_speech_ai.config import BASE_MODEL_NAME
        from risk_speech_ai.labels import LABELS, to_multi_hot
        from risk_speech_ai.train_cli import build_safe_training_samples, main as validation_cli
        from risk_speech_ai.dataset import RiskSpeechDataset, make_training_dataloader
        from risk_speech_ai.tokenization import load_koelectra_tokenizer, build_model_input
        from risk_speech_ai.checkpoint import tokenizer_metadata
        import risk_speech_ai.dataset as dataset_module

        check("project_venv_isolated", Path(sys.prefix).resolve() == (ROOT / ".venv-v2").resolve() and sys.prefix != sys.base_prefix)
        check("pinned_PR35_code_integrity", all(sha(REFERENCE / e["path"]) == e["sha256"] for e in manifest["files"]) and
              Path(dataset_module.__file__).resolve().is_relative_to(REFERENCE.resolve()))
        versions = {}
        for name in ("torch", "transformers", "tokenizers", "huggingface_hub", "numpy", "safetensors", "datasets"):
            try:
                versions[name] = importlib.metadata.version(name)
            except importlib.metadata.PackageNotFoundError:
                versions[name] = None
        report["environment"] = {"executable": sys.executable, "python": sys.version, "platform": platform.platform(),
                                  "venv": sys.prefix, "base_prefix": sys.base_prefix, "packages": versions,
                                  "cpu_execution": True, "cuda_available": torch.cuda.is_available(),
                                  "cuda_device_count": torch.cuda.device_count(), "torch_cuda_build": torch.version.cuda,
                                  "datasets_note": "Not installed: the actual loader uses PyTorch Dataset and JSONL; Hugging Face datasets is not imported."}
        torch.set_num_threads(2)
        candidates = jsonl(CANDIDATE)
        canonical = jsonl(protected[0])
        check("load_16_conversations_136_utterances", len(candidates) == 16 and sum(len(c["utterances"]) for c in candidates) == 136)
        check("canonical_structure_text_ids_labels_unchanged", [{k: v for k, v in c.items() if k != "review_preparation"} for c in candidates] == canonical)
        check("single_review_not_final_train_only", all(c["split"] == "train" and c["is_synthetic"] is True and
              c["review_preparation"]["final_approved"] is False and
              all(r["임정윤"] == "승인" and r["김해린"] == "미승인" and r["final_agreement"] == "미승인"
                  for r in c["review_preparation"]["reviewer_results"]) for c in candidates))
        adapter_dir = CANDIDATE.parent
        labels_path = adapter_dir / "v1_adapter_label_candidates.jsonl"
        tuned_path = adapter_dir / "v1_adapter_text_candidates.jsonl"
        label_rows, tuned_rows = jsonl(labels_path), jsonl(tuned_path)
        check("adapter_train_scope_and_identity", all(row["split"] == "train" and row["is_synthetic"] is True and row["final_approved"] is False
              for row in label_rows + tuned_rows) and len(label_rows) == len(tuned_rows) == 136)
        built, original_stats = build_safe_training_samples(label_rows, tuned_rows)
        check("actual_PR35_safe_builder_136_samples", len(built.samples) == 136 and built.statistics["included"] == 136 and built.statistics["invalid_label"] == 0,
              built.statistics)
        expected = {(c["synthetic_id"], u["utterance_id"]): (c, u) for c in candidates for u in c["utterances"]}
        for sample in built.samples:
            c, u = expected[sample.conversation_id, sample.utterance_id]
            start = max(0, sample.utterance_id - 1 - 5)
            assert sample.history_texts == [h["text"] for h in c["utterances"][start:sample.utterance_id - 1]]
            assert sample.current_text == u["text"] and sample.risk_target == float(u["is_phishing"])
            assert sample.type_targets == to_multi_hot(u["labels"])
        check("all_136_history_binary_and_8label_targets", True, {"max_previous": max(len(s.history_texts) for s in built.samples), "label_order": list(LABELS)})
        tokenizer = load_koelectra_tokenizer(REVISION)
        report["tokenizer"] = {"requested_revision": REVISION, "metadata": tokenizer_metadata(tokenizer)}
        v1_repro = json.loads((REFERENCE / "artifacts/risk_speech_ai/reports/reproducibility.json").read_text(encoding="utf-8"))
        report["tokenizer"]["vocabulary_fingerprint_matches_PR35_report"] = report["tokenizer"]["metadata"]["vocab_sha256"] == v1_repro["tokenizer_vocab_sha256"]
        prepared = [build_model_input(s.history_texts, s.current_text, tokenizer=tokenizer) for s in built.samples]
        check("real_pinned_tokenizer_136_inputs", len(prepared) == 136 and all(p.token_count <= 512 and len(p.input_ids) == len(p.attention_mask) == len(p.token_type_ids) for p in prepared))
        dataset = RiskSpeechDataset(built.samples, tokenizer=tokenizer)
        loader = make_training_dataloader(dataset, tokenizer=tokenizer, batch_size=4, shuffle=False)
        check("real_torch_DataLoader", isinstance(loader, torch.utils.data.DataLoader) and len(dataset) == 136,
              {"class": type(loader).__module__ + "." + type(loader).__qualname__, "batch_size": 4})
        batches = list(loader)
        check("real_minibatches_generated", len(batches) == 34 and sum(b["input_ids"].shape[0] for b in batches) == 136)
        offset = 0
        for batch in batches:
            size = batch["input_ids"].shape[0]
            assert batch["input_ids"].ndim == 2
            for key in ("input_ids", "attention_mask", "token_type_ids"):
                assert batch[key].dtype == torch.int64 and batch[key].shape == batch["input_ids"].shape
            assert batch["risk_target"].shape == (size, 1) and batch["risk_target"].dtype == torch.float32
            assert batch["type_targets"].shape == (size, 8) and batch["type_targets"].dtype == torch.float32
            assert torch.equal(batch["risk_target"], torch.tensor([[s.risk_target] for s in built.samples[offset:offset+size]], dtype=torch.float32))
            assert torch.equal(batch["type_targets"], torch.tensor([s.type_targets for s in built.samples[offset:offset+size]], dtype=torch.float32))
            for index, item in enumerate(prepared[offset:offset+size]):
                length = item.token_count
                assert batch["input_ids"][index, :length].tolist() == item.input_ids
                assert batch["attention_mask"][index, :length].tolist() == item.attention_mask
                assert batch["token_type_ids"][index, :length].tolist() == item.token_type_ids
                assert not batch["attention_mask"][index, length:].any()
            offset += size
        check("all_batch_shapes_dtypes_padding_and_labels", True)
        first = batches[0]
        report["minibatch"] = {"batch_size": 4, "batches_generated": len(batches), "dataset_size": len(dataset),
                               "first_batch": {key: {"shape": list(value.shape), "dtype": str(value.dtype), "device": str(value.device)} for key, value in first.items()},
                               "token_length_min": min(p.token_count for p in prepared), "token_length_max": max(p.token_count for p in prepared),
                               "max_original_history": max(len(s.history_texts) for s in built.samples),
                               "history_dropped_for_token_budget": sum(p.dropped_history_count for p in prepared),
                               "targets_with_dropped_history": sum(p.dropped_history_count > 0 for p in prepared),
                               "binary_positive": sum(s.risk_target for s in built.samples),
                               "type_positive_counts": dict(zip(LABELS, [sum(s.type_targets[i] for s in built.samples) for i in range(8)]))}
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = validation_cli(["--labels-jsonl", str(labels_path), "--tuned-jsonl", str(tuned_path), "--data-version", "v2-pilot-single-review-validation-only"])
        check("PR35_training_CLI_validation_only", code == 0 and "no model was trained" in output.getvalue())
        report["training_cli_validation_output"] = output.getvalue()
        patterns = ["test_training_data.py", "test_tokenization.py", "test_dataset.py", "test_metrics.py", "test_splits.py"]
        suite = unittest.TestSuite()
        test_loader = unittest.TestLoader()
        for pattern in patterns:
            suite.addTests(test_loader.discover(str(REFERENCE / "tests"), pattern=pattern))
        result = unittest.TextTestRunner(verbosity=1).run(suite)
        report["source_tests"] = {"run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped),
                                  "passed": result.testsRun - len(result.failures) - len(result.errors) - len(result.skipped), "patterns": patterns}
        check("PR35_non_training_tests", result.wasSuccessful())
        report["forward"] = {"status": "NOT_REQUESTED", "v1_checkpoint_validated": False}
        if args.random_forward:
            from transformers import AutoConfig, ElectraModel
            from risk_speech_ai.model import RiskSpeechClassifier
            config = AutoConfig.from_pretrained(BASE_MODEL_NAME, revision=REVISION, local_files_only=True)
            torch.manual_seed(42)
            model = RiskSpeechClassifier(encoder=ElectraModel(config)).eval()
            with torch.inference_mode():
                logits = model(first["input_ids"], first["attention_mask"], first["token_type_ids"])
            check("random_base_architecture_forward_no_training", tuple(logits.risk_logits.shape) == (4, 1) and tuple(logits.type_logits.shape) == (4, 8) and
                  bool(torch.isfinite(logits.risk_logits).all()) and bool(torch.isfinite(logits.type_logits).all()) and all(p.grad is None for p in model.parameters()))
            report["forward"] = {"status": "PASS_RANDOM_INITIALIZATION_ONLY", "architecture": "full pinned KoELECTRA base config",
                                 "risk_shape": list(logits.risk_logits.shape), "type_shape": list(logits.type_logits.shape),
                                 "parameter_count": sum(p.numel() for p in model.parameters()), "model_weights_downloaded": False,
                                 "v1_checkpoint_validated": False, "gradients_created": False, "accuracy_measured": False}
        check("protected_files_and_code_unchanged", all(sha(ROOT / path) == digest for path, digest in before.items()))
        report["status"] = "PASS_REAL_DATALOADER_NOT_FINAL_TRAINING_APPROVAL"
    except Exception as error:
        report.update(status="FAIL", exception=type(error).__name__, message=str(error))
        import traceback
        report["traceback"] = traceback.format_exc()
    report["check_counts"] = {"passed": sum(c["passed"] for c in checks), "failed": sum(not c["passed"] for c in checks)}
    report["protected_sha256"] = before
    report["protected_files_unchanged"] = all(sha(ROOT / path) == digest for path, digest in before.items())
    write_json(REPORTS / "real_minibatch_result.json", report)
    packages = subprocess.run([sys.executable, "-m", "pip", "freeze"], capture_output=True, text=True, encoding="utf-8")
    (REPORTS / "requirements-lock.txt").write_text(packages.stdout, encoding="utf-8")
    print(json.dumps({key: report.get(key) for key in ("status", "check_counts", "minibatch", "source_tests", "forward", "exception", "message", "protected_files_unchanged")}, ensure_ascii=False, indent=2))
    return 0 if report["status"].startswith("PASS") else 1


if __name__ == "__main__":
    raise SystemExit(main())
