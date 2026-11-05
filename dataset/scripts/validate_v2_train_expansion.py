#!/usr/bin/env python3
"""Validate a frozen TRAIN expansion and execute the real CPU DataLoader.

VALIDATION text is opened only after the new-data hash matches its generation
manifest. It is used only for post-generation overlap checks, never statistics,
generation, thresholds, model inference, or training.
"""
from __future__ import annotations

import copy
import csv
import hashlib
import importlib.metadata
import json
import math
import os
import re
import subprocess
import sys
import traceback
import unicodedata
from collections import Counter
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from itertools import combinations, product
from pathlib import Path

import prepare_v2_train_expansion as source
from prepare_pilot_review import COLUMNS, REVIEWERS
from restore_pilot import LABELS, UTTERANCE_FIELDS
from validate_masked import ALLOWED_TOKENS, VALID_SPEAKERS

ROOT, OUT, REPORTS = source.ROOT, source.OUT, source.REPORTS
REFERENCE = ROOT / "artifacts/v1_reference/pr35_9bab7e383928"
REVISION = "68b30cd259f34a4b5aa8786392612ba2a2617fcc"
VALIDATION = ROOT / "dataset/04. processed/v2_validation/validation_24_generated.jsonl"
CHECKS = []


def check(condition, name, detail=None):
    CHECKS.append(dict(name=name, passed=bool(condition), detail=detail))
    if not condition:
        raise ValueError(name)


def no_duplicate_keys(pairs):
    result = {}
    for k, v in pairs:
        if k in result:
            raise ValueError(f"Duplicate JSON key: {k}")
        result[k] = v
    return result


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=no_duplicate_keys)


def jsonl(path):
    lines = path.read_text(encoding="utf-8").splitlines()
    check(bool(lines) and all(line.strip() for line in lines), f"no_blank_jsonl:{path.name}")
    rows = [json.loads(line, object_pairs_hook=no_duplicate_keys) for line in lines]
    check(all(isinstance(r, dict) for r in rows), f"json_objects:{path.name}")
    return rows


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")


def stats(conversations):
    utterances = [u for c in conversations for u in c["utterances"]]
    positive = Counter(label for u in utterances for label in u["labels"])
    return dict(conversations=len(conversations), utterances=len(utterances),
                phishing=sum(u["is_phishing"] for u in utterances), normal=sum(not u["is_phishing"] for u in utterances),
                entirely_normal_conversations=sum(not any(u["is_phishing"] for u in c["utterances"]) for c in conversations),
                labels={label: positive[label] for label in LABELS},
                multi_label_utterances=sum(len(u["labels"]) > 1 for u in utterances))


def validate_structure(new, old, merged):
    check(len(new) == 8 and len(old) == 16 and len(merged) == 24, "8_new_16_old_24_merged")
    check(merged == old+new, "merged_records_equal_old_plus_new")
    check(source.MERGED.read_bytes() == source.PREVIOUS.read_bytes()+source.NEW.read_bytes(), "old_16_candidate_bytes_and_review_history_preserved")
    canonical = jsonl(source.PILOT)
    check([{k: v for k, v in c.items() if k != "review_preparation"} for c in old] == canonical, "old16_canonical_text_labels_ids_unchanged")
    check(all(c["review_preparation"]["completed_reviewers"] == ["임정윤"]
              and c["review_preparation"]["final_approved"] is False
              and all(r["임정윤"] == "승인" and r["김해린"] == "미승인" and r["final_agreement"] == "미승인"
                      for r in c["review_preparation"]["reviewer_results"]) for c in old), "old16_single_review_not_final_state_retained")
    check([c["synthetic_id"] for c in merged] == [f"SYN2-TRAIN-{i:04}" for i in range(1, 25)], "train_0001_to_0024_no_validation_mix")
    for key in ("synthetic_id", "scenario_family_id", "scenario_id"):
        check(len({c[key] for c in merged}) == 24, f"unique_merged:{key}")
    composite = []
    for c in merged:
        cid = c["synthetic_id"]
        check(c["split"] == "train" and c["is_synthetic"] is True and c["actual_call"] is False
              and c["review_status"] == "generated" and c["source_kind"] == "llm_simulation", f"synthetic_train_generated:{cid}")
        check(8 <= len(c["utterances"]) <= 10, f"utterance_count:{cid}")
        for position, u in enumerate(c["utterances"], 1):
            uid = f"{cid}-{position}"
            composite.append((cid, u["utterance_id"]))
            check(set(u) == UTTERANCE_FIELDS and type(u["utterance_id"]) is int and u["utterance_id"] == position
                  and u["speaker"] in VALID_SPEAKERS, f"fields_order_speaker:{uid}")
            check(isinstance(u["text"], str) and bool(u["text"].strip()) and isinstance(u["label_rationale"], str)
                  and bool(u["label_rationale"].strip()), f"text_rationale:{uid}")
            check(type(u["is_phishing"]) is bool and isinstance(u["labels"], list)
                  and all(label in LABELS for label in u["labels"]) and len(set(u["labels"])) == len(u["labels"])
                  and u["is_phishing"] == bool(u["labels"]), f"labels_consistent:{uid}")
            check(set(re.findall(r"\[([^\]]+)\]", u["text"])) <= ALLOWED_TOKENS
                  and not re.search(r"(?:\d[ -]?){7,}|https?://|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", u["text"]), f"masking_and_no_literal_identifiers:{uid}")
    check(len(set(composite)) == len(composite), "unique_composite_utterance_ids")
    for i, c in enumerate(new, 17):
        check(set(c) == set(canonical[0]), f"new_actual_canonical_fields:{i}")
        check(c["scenario_family_id"] == f"FAM2-TRAIN-{i:04}" and c["generation_model"] == source.MODEL
              and c["split_version"] == c["prompt_version"] == "v2-train-expansion-1"
              and c["variant_id"] == "original", f"new_generation_metadata:{i}")
        check(c["revision_history"] and all(r["human_approved"] is False and r["revision_model"] == source.MODEL
              and r["changed_utterance_ids"] == list(range(1, len(c["utterances"])+1)) for r in c["revision_history"]), f"new_no_human_approval:{i}")
        labels = {label for u in c["utterances"] for label in u["labels"]}
        check((c["primary_type"] is None and not labels) or c["primary_type"] in labels, f"primary_type:{i}")
    return dict(existing16=stats(old), new8=stats(new), merged24=stats(merged))


def validate_review(new):
    check(source.CSV.read_bytes().startswith(b"\xef\xbb\xbf"), "review_csv_utf8_bom")
    with source.CSV.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        check(reader.fieldnames == COLUMNS, "reuse_train_review_columns")
        rows = list(reader)
    check(rows == source.review_rows(new), "new_csv_all_source_rows_and_all_unapproved")
    return dict(rows=len(rows), reviewers={name: dict(Counter(r[f"검수_결과_{name}"] for r in rows)) for name in REVIEWERS},
                final_agreement=dict(Counter(r["최종_합의_결과"] for r in rows)), training_applied=False)


def normalize(text):
    return "".join(ch for ch in unicodedata.normalize("NFKC", text).casefold()
                   if not ch.isspace() and not unicodedata.category(ch).startswith("P"))


def flatten(conversations, transcript=False):
    if transcript:
        return [dict(id=c["synthetic_id"], text="\n".join(u["text"] for u in c["utterances"])) for c in conversations]
    return [dict(id=f"{c['synthetic_id']}-{u['utterance_id']}", text=u["text"]) for c in conversations for u in c["utterances"]]


def compare(pairs):
    candidates, highest, count = [], None, 0
    for a, b in pairs:
        count += 1
        aa, bb = normalize(a["text"]), normalize(b["text"])
        ratio = SequenceMatcher(None, aa, bb, autojunk=False).ratio()
        row = dict(left=a["id"], right=b["id"], similarity=round(ratio, 6), left_text=a["text"], right_text=b["text"])
        if highest is None or ratio > highest["similarity"]:
            highest = row
        if a["text"] == b["text"] or aa == bb or ratio >= .80:
            row["kind"] = "exact" if a["text"] == b["text"] else "normalized_only" if aa == bb else "similar_at_080"
            candidates.append(row)
    return dict(pairs_checked=count, candidate_count=len(candidates), kinds=dict(Counter(r["kind"] for r in candidates)),
                candidates=candidates, highest_similarity_pair=highest)


def duplicates(new, old, merged, provenance):
    # Immutable-generation gate precedes the only read of VALIDATION utterances.
    check(source.sha(source.NEW) == provenance["new8_sha256_before_post_generation_validation_audit"]
          and source.sha(source.MERGED) == provenance["merged24_sha256_before_post_generation_validation_audit"], "new_train_frozen_before_validation_text_access")
    registry = read_json(source.RESERVED)
    validation = jsonl(VALIDATION)
    check(len(validation) == 24 and all(c["split"] == "validation" for c in validation), "validation_read_for_post_generation_overlap_only")
    check(len(registry["scenarios"]) == 24 and all(any(c["synthetic_id"] == d["synthetic_id"]
          and c["scenario_family_id"] == d["scenario_family_id"] and c["scenario_id"] == d["scenario_id"] for c in validation)
          for d in registry["scenarios"]), "validation_registry_matches_ids")
    collisions = {key: sorted({c[key] for c in merged} & {c[key] for c in validation})
                  for key in ("synthetic_id", "scenario_family_id", "scenario_id")}
    check(not any(collisions.values()), "no_train_validation_id_family_scenario_collision", collisions)
    n, o, m, v = map(flatten, (new, old, merged, validation))
    result = dict(normalization="NFKC + casefold; remove whitespace and Unicode punctuation",
                  metric="SequenceMatcher(autojunk=False), report all candidates >=0.80 including exact/normalized",
                  validation_usage="Post-generation comparisons only; no VALIDATION label statistics or design feedback",
                  validation_sha256=source.sha(VALIDATION), collisions=collisions,
                  new_vs_existing_train=compare(product(n, o)), new_internal=compare(combinations(n, 2)),
                  existing_train_internal=compare(combinations(o, 2)), merged_train_internal=compare(combinations(m, 2)),
                  new_vs_validation=compare(product(n, v)), merged_vs_validation=compare(product(m, v)),
                  new_full_transcript_vs_existing=compare(product(flatten(new, True), flatten(old, True))),
                  new_full_transcript_vs_validation=compare(product(flatten(new, True), flatten(validation, True))),
                  new_full_transcript_internal=compare(combinations(flatten(new, True), 2)),
                  actual_v1_overlap="NOT_VERIFIED_INPUTS_UNAVAILABLE", test_overlap="TEST_NOT_CREATED",
                  semantic_status="AUTHOR_SCENARIO_COMPARISON_ONLY_HUMAN_REVIEW_PENDING",
                  semantic_limitation="Lexical comparisons do not establish paraphrase or plot independence. Review scenario_design.md and scenario_independence_review.md.",
                  deletion_policy="All candidates retained and reported; preexisting duplicate text and labels are unchanged")
    write_json(REPORTS / "duplicate_report.json", result)
    new_names = ("new_vs_existing_train", "new_internal", "new_vs_validation", "new_full_transcript_vs_existing", "new_full_transcript_vs_validation", "new_full_transcript_internal")
    result["new_overlap_review_required"] = any(result[k]["candidate_count"] for k in new_names)
    check(source.sha(source.NEW) == provenance["new8_sha256_before_post_generation_validation_audit"], "no_train_edit_after_validation_comparison")
    return result


def dry_run_samples(conversations, sample_type, to_multi_hot):
    """Convert all rows solely to check execution, never change review status."""
    samples, labels, texts, context = [], [], [], []
    old_adapter = { (r["conversation_id"], r["utterance_id"]): r for r in source.jsonl(source.PREVIOUS.parent / "v1_adapter_label_candidates.jsonl") }
    for c in conversations:
        if c["split"] != "train" or c["review_status"] != "generated":
            raise ValueError("Only generated TRAIN candidates accepted for dry run")
        for offset, u in enumerate(c["utterances"]):
            key = c["synthetic_id"], u["utterance_id"]
            history = c["utterances"][max(0, offset-5):offset]
            sample = sample_type(*key, [h["text"] for h in history], u["text"], float(u["is_phishing"]), to_multi_hot(u["labels"]))
            samples.append(sample)
            provenance = dict(conversation_id=key[0], utterance_id=key[1], split="train", is_synthetic=True,
                actual_call=False, scenario_family_id=c["scenario_family_id"], review_status="generated",
                final_approved=False, execution_check_only=True, training_authorized=False, training_eligible=False,
                human_review_stage="single_review_train_candidate" if "review_preparation" in c else "generated_unreviewed")
            label = copy.deepcopy(old_adapter[key]) if "review_preparation" in c else dict(label_status="unreviewed", is_phishing=u["is_phishing"], labels=u["labels"])
            labels.append({**label, **provenance})
            texts.append({**provenance, "tuned_text": u["text"], "text_transform": "identity_from_candidate"})
            context.append({**provenance, "history_utterance_ids": [h["utterance_id"] for h in history]})
    return samples, labels, texts, context


def minibatch(merged):
    hf = ROOT / "artifacts/v2_runtime_assets/hf"
    os.environ.update(HF_HOME=str(hf), HF_HUB_CACHE=str(hf / "hub"), HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", HF_HUB_DISABLE_TELEMETRY="1")
    sys.path.insert(0, str(REFERENCE))
    import torch
    import risk_speech_ai.dataset as runtime_dataset
    from risk_speech_ai.dataset import RiskSpeechDataset, make_training_dataloader
    from risk_speech_ai.training_data import TrainingSample
    from risk_speech_ai.train_cli import build_safe_training_samples
    from risk_speech_ai.labels import LABELS as runtime_labels, to_multi_hot
    from risk_speech_ai.tokenization import load_koelectra_tokenizer, build_model_input
    from risk_speech_ai.checkpoint import tokenizer_metadata

    manifest = read_json(REFERENCE / "source_manifest.json")
    check(Path(runtime_dataset.__file__).resolve().is_relative_to(REFERENCE.resolve())
          and all(source.sha(REFERENCE / e["path"]) == e["sha256"] for e in manifest["files"]), "pinned_runtime_code_hashes")
    check(Path(sys.prefix).resolve() == (ROOT / ".venv-v2").resolve() and sys.prefix != sys.base_prefix, "reuse_venv_v2")
    check(tuple(runtime_labels) == LABELS, "eight_label_order_matches")
    torch.set_num_threads(2)
    samples, labels, texts, contexts = dry_run_samples(merged, TrainingSample, to_multi_hot)
    safe, initial = build_safe_training_samples(labels, texts)
    old_count = sum(len(c["utterances"]) for c in merged if "review_preparation" in c)
    new_count = len(samples)-old_count
    # The first pass excludes unreviewed labels. The second safe pass removes
    # their text too, so its counters report missing text, not another exclusion.
    check(len(safe.samples) == old_count == 136 and initial["excluded_unreviewed"] == new_count == 72
          and safe.statistics["matched"] == 136 and safe.statistics["missing_tuned_text"] == 72
          and safe.statistics["invalid_label"] == 0,
          "normal_safe_builder_keeps136_and_rejects72_unreviewed", dict(initial=initial, safe=safe.statistics))
    check(all(s.conversation_id in {c["synthetic_id"] for c in merged[:16]} for s in safe.samples)
          and all(not r["training_eligible"] and not r["training_authorized"] for r in labels), "dry_run_is_not_training_approval")
    source.dump_jsonl(OUT / "cpu_dry_run_label_candidates.jsonl", labels)
    source.dump_jsonl(OUT / "cpu_dry_run_text_candidates.jsonl", texts)
    source.dump_jsonl(OUT / "context_audit.jsonl", contexts)
    tokenizer = load_koelectra_tokenizer(REVISION)
    metadata = tokenizer_metadata(tokenizer)
    expected_vocab = read_json(REFERENCE / "artifacts/risk_speech_ai/reports/reproducibility.json")["tokenizer_vocab_sha256"]
    check(metadata["vocab_sha256"] == expected_vocab, "pinned_tokenizer_vocab_fingerprint")
    prepared = [build_model_input(s.history_texts, s.current_text, tokenizer=tokenizer) for s in samples]
    dataset = RiskSpeechDataset(samples, tokenizer=tokenizer)
    loader = make_training_dataloader(dataset, tokenizer=tokenizer, batch_size=4, shuffle=False)
    check(isinstance(loader, torch.utils.data.DataLoader) and len(dataset) == len(samples), "real_pytorch_DataLoader")
    indexed = {(c["synthetic_id"], u["utterance_id"]): (c, u) for c in merged for u in c["utterances"]}
    first, offset, batch_count = None, 0, 0
    for batch in loader:
        batch_count += 1
        size, width = batch["input_ids"].shape
        check(0 < size <= 4 and width <= 512 and all(v.device.type == "cpu" for v in batch.values()), f"cpu_batch_length:{batch_count}")
        check(all(batch[k].dtype == torch.int64 and tuple(batch[k].shape) == (size, width)
                  for k in ("input_ids", "attention_mask", "token_type_ids")), f"input_shape_dtype:{batch_count}")
        check(tuple(batch["risk_target"].shape) == (size, 1) and batch["risk_target"].dtype == torch.float32
              and tuple(batch["type_targets"].shape) == (size, 8) and batch["type_targets"].dtype == torch.float32, f"target_shapes_dtype:{batch_count}")
        expected = samples[offset:offset+size]
        check(torch.equal(batch["risk_target"], torch.tensor([[s.risk_target] for s in expected], dtype=torch.float32))
              and torch.equal(batch["type_targets"], torch.tensor([s.type_targets for s in expected], dtype=torch.float32)), f"all_batch_targets:{batch_count}")
        for row, sample in enumerate(expected):
            c, u = indexed[sample.conversation_id, sample.utterance_id]
            check(sample.current_text == u["text"] and sample.risk_target == float(u["is_phishing"])
                  and sample.type_targets == to_multi_hot(u["labels"])
                  and sample.history_texts == [h["text"] for h in c["utterances"][max(0, u["utterance_id"]-6):u["utterance_id"]-1]], f"source_history_and_targets:{offset+row}")
            item = prepared[offset+row]
            n = item.token_count
            check(all(batch[k][row, :n].tolist() == getattr(item, k) for k in ("input_ids", "attention_mask", "token_type_ids"))
                  and not batch["attention_mask"][row, n:].any() and not batch["token_type_ids"][row, n:].any()
                  and all(v == tokenizer.pad_token_id for v in batch["input_ids"][row, n:].tolist()), f"tokens_masks_padding:{offset+row}")
        if first is None:
            first = {k: dict(shape=list(v.shape), dtype=str(v.dtype), device=str(v.device)) for k, v in batch.items()}
        offset += size
    check(offset == len(samples) == 208 and batch_count == math.ceil(len(samples)/4), "all208_samples_all52_batches")
    return dict(status="PASS_CPU_DATALOADER_DRY_RUN_ONLY", conversations=len(merged), samples=offset, batches=batch_count,
        batch_size=4, first_batch=first, label_order=list(LABELS), max_history=max(len(s.history_texts) for s in samples),
        history_verified_targets=offset, token_length_min=min(p.token_count for p in prepared), token_length_max=max(p.token_count for p in prepared),
        dropped_history=sum(p.dropped_history_count for p in prepared), tokenizer_revision=REVISION, tokenizer=metadata,
        runtime_revision=manifest["revision"], regular_safe_builder=dict(samples=len(safe.samples), statistics=safe.statistics, initial=initial),
        adapter_policy="All208 typed samples for execution checks only; preserve existing one-review labels, leave new72 unreviewed; never call training CLI",
        environment=dict(executable=sys.executable, python=sys.version, torch=torch.__version__,
            transformers=importlib.metadata.version("transformers")))


def preservation():
    baseline = read_json(REPORTS / "protected_baseline.json")
    changed = [p for p, digest in baseline["files"].items() if not (ROOT/p).is_file() or source.sha(ROOT/p) != digest]
    check(not changed, "preexisting_files_unchanged", dict(files=len(baseline["files"]), changed=changed))
    check(subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, cwd=ROOT).strip() == baseline["head"]
          and subprocess.check_output(["git", "branch", "--show-current"], text=True, cwd=ROOT).strip() == baseline["branch"], "git_branch_head_preserved")
    return dict(files=len(baseline["files"]), changed=changed, head=baseline["head"], branch=baseline["branch"])


def main():
    report = dict(status="RUNNING", checked_at=datetime.now(timezone(timedelta(hours=9))).isoformat(), checks=CHECKS,
        training_executed=False, model_loaded=False, checkpoint_changed=False, threshold_optimized=False, human_approval_assigned=False,
        training_readiness="NOT_READY_NEW8_UNREVIEWED_OLD16_SINGLE_REVIEW_ONLY", actual_v1_overlap="NOT_VERIFIED_INPUTS_UNAVAILABLE")
    try:
        report["preservation_before"] = preservation()
        new, old, merged = map(jsonl, (source.NEW, source.PREVIOUS, source.MERGED))
        provenance = read_json(OUT / "generation_and_scenarios.json")
        check(provenance["training_authorized"] is False and provenance["final_approved"] is False, "manifest_not_approved_for_training")
        check(all(source.sha(ROOT/p) == digest for p, digest in provenance["generation_inputs"].items()), "generation_input_hashes")
        check(provenance["scenarios"] == source.DESIGNS and len(provenance["scenarios"]) == 8, "scenario_design_coverage")
        report["statistics"] = validate_structure(new, old, merged)
        report["review_csv"] = validate_review(new)
        overlaps = duplicates(new, old, merged, provenance)
        report["duplicates"] = {k: dict(candidate_count=v["candidate_count"], kinds=v["kinds"], pairs_checked=v["pairs_checked"])
                               for k, v in overlaps.items() if isinstance(v, dict) and "candidate_count" in v}
        report["id_collisions"] = overlaps["collisions"]
        report["new_overlap_review_required"] = overlaps["new_overlap_review_required"]
        report["minibatch"] = minibatch(merged)
        report["preservation_after"] = preservation()
        check(source.sha(source.NEW) == provenance["new8_sha256_before_post_generation_validation_audit"]
              and source.sha(source.MERGED) == provenance["merged24_sha256_before_post_generation_validation_audit"], "frozen_new_and_merged_unchanged_after_all_audits")
        report["status"] = "PASS_EXECUTION_DUPLICATE_CANDIDATES_NEED_REVIEW" if overlaps["new_overlap_review_required"] else "PASS_AUTOMATION_HUMAN_REVIEW_PENDING"
    except Exception as error:
        report.update(status="FAIL", exception=type(error).__name__, message=str(error), traceback=traceback.format_exc())
    report["check_counts"] = dict(passed=sum(c["passed"] for c in CHECKS), failed=sum(not c["passed"] for c in CHECKS))
    write_json(REPORTS / "validation_result.json", report)
    print(json.dumps({k: v for k, v in report.items() if k not in ("checks", "traceback")}, ensure_ascii=False, indent=2))
    if report["status"] == "FAIL":
        print(report["traceback"], file=sys.stderr)
    return int(report["status"] == "FAIL")


if __name__ == "__main__":
    raise SystemExit(main())
