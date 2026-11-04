#!/usr/bin/env python3
"""Run non-training adapter tests and attempt a real offline DataLoader batch.

Never run training/integration optimizer tests, initialize a model, or create a
checkpoint. Missing dependencies/assets are reported, never replaced by mocks.
"""
import ast
import importlib.metadata
import importlib.util
import json
import os
import platform
import subprocess
import sys
import unittest
from pathlib import Path

import prepare_v2_training_candidate as prep


def run_tests(directory, patterns):
    suite = unittest.TestSuite()
    loader = unittest.TestLoader()
    for pattern in patterns:
        suite.addTests(loader.discover(str(directory), pattern=pattern))
    # One original contract test patches the real transformers import path.
    # Keep its missing dependency explicit rather than injecting a fake package.
    if importlib.util.find_spec("transformers") is None and "test_tokenization" in sys.modules:
        cls = sys.modules["test_tokenization"].PairTests
        name = "test_koelectra_loader_passes_requested_revision_to_both_assets"
        setattr(cls, name, unittest.skip("transformers not installed; real import path cannot be tested")(getattr(cls, name)))
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    return {"tests": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
            "skipped": len(result.skipped), "success": result.wasSuccessful()}


def main():
    prep.load_reference()
    existing = prep.REPORTS / "execution_result.json"
    initial = prep.REPORTS / "execution_initial_attempt.json"
    if existing.exists() and not initial.exists():
        initial.write_bytes(existing.read_bytes())
    versions = {}
    for package in ("torch", "transformers", "tokenizers", "huggingface_hub"):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = None
    tests = run_tests(prep.REFERENCE / "tests", ["test_training_data.py", "test_tokenization.py"])
    # Reset discovery root for the project tests.
    loader = unittest.TestLoader()
    suite = loader.discover(str(prep.ROOT / "tests"), pattern="test_v2_training_candidate.py")
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    adapter_tests = {"tests": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
                     "skipped": len(result.skipped), "success": result.wasSuccessful()}
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    batch_result = {"status": "NOT_EXECUTED", "mock_tokenizer_used_for_actual_batch": False}
    try:
        from risk_speech_ai.dataset import RiskSpeechDataset, make_training_dataloader
        from risk_speech_ai.tokenization import load_koelectra_tokenizer
        labels = [json.loads(line) for line in (prep.OUTPUT / "v1_adapter_label_candidates.jsonl").read_text(encoding="utf-8").splitlines()]
        tuned = [json.loads(line) for line in (prep.OUTPUT / "v1_adapter_text_candidates.jsonl").read_text(encoding="utf-8").splitlines()]
        module, _ = prep.load_reference()
        built = module.build_training_samples(labels, tuned)
        tokenizer = load_koelectra_tokenizer()
        dataset = RiskSpeechDataset(built.samples, tokenizer=tokenizer)
        batch = next(iter(make_training_dataloader(dataset, tokenizer=tokenizer, batch_size=8, shuffle=False)))
        batch_result = {"status": "PASS", "dataset_size": len(dataset),
                        "shapes": {key: list(value.shape) for key, value in batch.items()},
                        "mock_tokenizer_used_for_actual_batch": False, "model_initialized": False}
    except (ImportError, RuntimeError, OSError) as error:
        batch_result.update(status="BLOCKED_RUNTIME_OR_CACHED_ASSETS", exception=type(error).__name__, message=str(error))
    dependency_probe = subprocess.run([
        sys.executable, "-B", "-X", "utf8", "-m", "pip", "--isolated", "index", "versions", "torch",
        "--index-url", "https://download.pytorch.org/whl/cpu", "--retries", "0", "--timeout", "10",
    ], capture_output=True, text=True, encoding="utf-8", errors="replace")
    inventory = {}
    for path in sorted((prep.REFERENCE / "risk_speech_ai").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        inventory[path.name] = [node.name for node in tree.body if isinstance(node, (ast.ClassDef, ast.FunctionDef))]
    report = {"python": sys.version, "platform": platform.platform(), "dependencies": versions,
              "recovered_source_contract_tests": tests, "new_adapter_tests": adapter_tests,
              "actual_minibatch": batch_result, "source_api_inventory": inventory,
              "dependency_index_probe": {"exit_code": dependency_probe.returncode,
                                          "stdout": dependency_probe.stdout, "stderr": dependency_probe.stderr,
                                          "installed_packages": False},
              "training_called": False, "optimizer_steps": 0, "model_forward_executed": False,
              "checkpoint_written": False,
              "test_scope": "Recovered training_data/tokenization contract tests use their original test tokenizers. They do not establish real KoELECTRA tokenization. Original model/training tests that execute backward/optimizer steps were intentionally not run."}
    prep.write_json(prep.REPORTS / "execution_result.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if tests["success"] and adapter_tests["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
