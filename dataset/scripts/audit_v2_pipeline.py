#!/usr/bin/env python3
"""Read-only pipeline/review/split audit; no training or source-data writes."""
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import subprocess
import sys
import traceback
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from difflib import SequenceMatcher
from itertools import product
from pathlib import Path

from v2_pipeline_gate import approval_audit, prepare_partition, PipelineGateError, validate_partition
from prepare_pilot_review import COLUMNS, REVIEWERS
from restore_pilot import LABELS

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "reports/v2_pipeline_audit"
REF = ROOT / "artifacts/v1_reference/pr35_9bab7e383928"
TRAIN = ROOT / "dataset/04. processed/v2_train_expansion/train_24_mixed_review_candidate.jsonl"
VALIDATION = ROOT / "dataset/04. processed/v2_validation/validation_24_generated.jsonl"
RECOVERED = ROOT / "artifacts/v1_recovered_8faa6a7eebfe/prepared"
REVISION = "68b30cd259f34a4b5aa8786392612ba2a2617fcc"
CHECKS = []


def check(condition, name, detail=None):
    CHECKS.append(dict(name=name, passed=bool(condition), detail=detail))
    if not condition:
        raise ValueError(name)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def no_duplicate_keys(pairs):
    result = {}
    for k, v in pairs:
        if k in result:
            raise ValueError(f"Duplicate JSON key: {k}")
        result[k] = v
    return result


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=no_duplicate_keys)


def read_jsonl(path):
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    check(bool(lines) and all(line.strip() for line in lines), f"valid_nonblank_jsonl:{path.name}")
    return [json.loads(line, object_pairs_hook=no_duplicate_keys) for line in lines]


def write_json(name, data):
    (OUT/name).write_text(json.dumps(data, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")


def review_rows(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        check(reader.fieldnames == COLUMNS, f"existing_review_columns:{path.parent.name}")
        return list(reader)


def normalize(text):
    return "".join(ch for ch in unicodedata.normalize("NFKC", text).casefold()
                   if not ch.isspace() and not unicodedata.category(ch).startswith("P"))


def utterances(conversations):
    return [dict(id=f"{c['synthetic_id']}-{u['utterance_id']}", conversation_id=c["synthetic_id"], text=u["text"],
                 normalized=normalize(u["text"])) for c in conversations for u in c["utterances"]]


def compare(left, right):
    """Exact exhaustive threshold screen with safe upper-bound pruning.

    Bounds can only reject ratios <0.80; never claim a global highest ratio when
    pruned pairs were not fully scored. Both exact/normalized matches are kept.
    """
    candidates, full_scores, count = [], 0, 0
    for a, b in product(left, right):
        count += 1
        aa, bb = a["normalized"], b["normalized"]
        if aa == bb:
            ratio = 1.0
        else:
            sm = SequenceMatcher(None, aa, bb, autojunk=False)
            if sm.real_quick_ratio() < .80 or sm.quick_ratio() < .80:
                continue
            full_scores += 1
            ratio = sm.ratio()
        if ratio >= .80:
            candidates.append(dict(left=a["id"], right=b["id"], left_text=a["text"], right_text=b["text"],
                similarity=round(ratio, 6), kind="exact" if a["text"] == b["text"] else "normalized_only" if aa == bb else "similar_at_080"))
    return dict(pairs_checked=count, ratios_computed_after_bounds=full_scores, candidate_count=len(candidates),
                kinds=dict(Counter(c["kind"] for c in candidates)), candidates=candidates)


def legacy_rows(conversations):
    labels, texts = [], []
    old = {(r["conversation_id"], r["utterance_id"]): r for r in read_jsonl(ROOT / "dataset/04. processed/v2_pilot/training_candidate/v1_adapter_label_candidates.jsonl")}
    for c in conversations:
        for u in c["utterances"]:
            key = c["synthetic_id"], u["utterance_id"]
            status = old[key]["label_status"] if key in old else "unreviewed"
            common = dict(conversation_id=key[0], utterance_id=key[1], split=c["split"], final_approved=False,
                          training_eligible=False, execution_check_only=True)
            labels.append({**common, "label_status": status, "is_phishing": u["is_phishing"], "labels": u["labels"]})
            texts.append({**common, "tuned_text": u["text"]})
    return labels, texts


def run_partition(conversations, split, tokenizer, runtime):
    torch, Sample, multi_hot, Dataset, loader_factory, tokenize = runtime
    partition = prepare_partition(conversations, split=split, mode="preflight", sample_type=Sample, to_multi_hot=multi_hot)
    check(not partition.training_allowed and partition.split == split, f"preflight_not_training:{split}")
    samples = partition.samples
    dataset = Dataset(samples, tokenizer=tokenizer)
    loader = loader_factory(dataset, tokenizer=tokenizer, batch_size=4, shuffle=False)
    check(isinstance(loader, torch.utils.data.DataLoader), f"actual_DataLoader:{split}")
    prepared = [tokenize(s.history_texts, s.current_text, tokenizer=tokenizer) for s in samples]
    lookup = {(c["synthetic_id"], u["utterance_id"]): (c, u) for c in conversations for u in c["utterances"]}
    offset, batches, first, contexts = 0, 0, None, []
    for batch in loader:
        batches += 1
        n, width = batch["input_ids"].shape
        check(all(v.device.type == "cpu" for v in batch.values()) and 0 < n <= 4 and width <= 512, f"cpu_size_length:{split}:{batches}")
        check(all(batch[k].dtype == torch.int64 and tuple(batch[k].shape) == (n, width) for k in ("input_ids", "attention_mask", "token_type_ids")), f"input_shapes_dtypes:{split}:{batches}")
        check(tuple(batch["risk_target"].shape) == (n, 1) and batch["risk_target"].dtype == torch.float32
              and tuple(batch["type_targets"].shape) == (n, 8) and batch["type_targets"].dtype == torch.float32, f"target_shapes_dtypes:{split}:{batches}")
        expected = samples[offset:offset+n]
        check(torch.equal(batch["risk_target"], torch.tensor([[s.risk_target] for s in expected], dtype=torch.float32))
              and torch.equal(batch["type_targets"], torch.tensor([s.type_targets for s in expected], dtype=torch.float32)), f"all_target_values:{split}:{batches}")
        for row, sample in enumerate(expected):
            c, u = lookup[sample.conversation_id, sample.utterance_id]
            history = c["utterances"][max(0, u["utterance_id"]-6):u["utterance_id"]-1]
            check(sample.current_text == u["text"] and sample.risk_target == float(u["is_phishing"])
                  and sample.type_targets == multi_hot(u["labels"]) and sample.history_texts == [h["text"] for h in history], f"same_conversation_history_and_current:{split}:{offset+row}")
            item = prepared[offset+row]
            length = item.token_count
            check(all(batch[k][row, :length].tolist() == getattr(item, k) for k in ("input_ids", "attention_mask", "token_type_ids"))
                  and not batch["attention_mask"][row, length:].any() and not batch["token_type_ids"][row, length:].any()
                  and all(i == tokenizer.pad_token_id for i in batch["input_ids"][row, length:].tolist()), f"tokens_masks_padding:{split}:{offset+row}")
            # Pair formatting: CLS history SEP current SEP; current segment is 1.
            boundary = item.token_type_ids.index(1)
            check(item.input_ids[0] == tokenizer.cls_token_id and item.input_ids[boundary-1] == tokenizer.sep_token_id
                  and item.input_ids[-1] == tokenizer.sep_token_id and set(item.token_type_ids[:boundary]) == {0}
                  and set(item.token_type_ids[boundary:]) == {1}, f"actual_sentence_pair_contract:{split}:{offset+row}")
            contexts.append(dict(split=split, conversation_id=c["synthetic_id"], utterance_id=u["utterance_id"],
                history_utterance_ids=[h["utterance_id"] for h in history], token_count=length,
                current_text_sha256=hashlib.sha256(u["text"].encode("utf-8")).hexdigest(), mode="preflight", training_allowed=False))
        if first is None:
            first = {k: dict(shape=list(v.shape), dtype=str(v.dtype), device=str(v.device)) for k, v in batch.items()}
        offset += n
    check(offset == len(samples) and batches == math.ceil(len(samples)/4), f"all_samples_batches:{split}")
    with (OUT/f"{split}_context_audit.jsonl").open("w", encoding="utf-8", newline="\n") as stream:
        for row in contexts:
            stream.write(json.dumps(row, ensure_ascii=False)+"\n")
    return dict(status="READY_PREFLIGHT_ONLY", conversations=len(conversations), samples=offset, batches=batches, batch_size=4,
        first_batch=first, max_history=max(len(s.history_texts) for s in samples),
        token_length_min=min(p.token_count for p in prepared), token_length_max=max(p.token_count for p in prepared),
        dropped_history=sum(p.dropped_history_count for p in prepared), training_allowed=False)


def integrity():
    base = read_json(OUT / "protected_baseline.json")
    changed = [p for p, digest in base["files"].items() if not (ROOT/p).is_file() or sha(ROOT/p) != digest]
    check(not changed, "preexisting_files_preserved", dict(files=len(base["files"]), changed=changed))
    check(subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, cwd=ROOT).strip() == base["head"], "git_HEAD_unchanged")
    check(subprocess.check_output(["git", "branch", "--show-current"], text=True, cwd=ROOT).strip() == base["branch"], "git_branch_unchanged")
    return dict(files=len(base["files"]), changed=changed)


def main():
    report = dict(status="RUNNING", checked_at=datetime.now(timezone(timedelta(hours=9))).isoformat(), checks=CHECKS,
        training_executed=False, checkpoint_loaded=False, threshold_optimized=False, human_approval_assigned=False,
        synthetic_data_generated=False)
    try:
        report["preservation_before"] = integrity()
        train, val = read_jsonl(TRAIN), read_jsonl(VALIDATION)
        validate_partition(train, "train")
        validate_partition(val, "validation")
        check(len(train) == len(val) == 24 and sum(len(c["utterances"]) for c in train) == 208
              and sum(len(c["utterances"]) for c in val) == 192, "24_train_208_and24_validation192_total400")
        prefix = ROOT / "dataset/04. processed/v2_pilot/training_candidate/pilot_single_review_train_candidate.jsonl"
        new = ROOT / "dataset/04. processed/v2_train_expansion/train_0017_0024_generated.jsonl"
        check(TRAIN.read_bytes() == prefix.read_bytes()+new.read_bytes(), "old16_and_new8_bytes_unchanged")
        collisions = {k: sorted({c[k] for c in train}&{c[k] for c in val}) for k in ("synthetic_id", "scenario_family_id", "scenario_id")}
        check(not any(collisions.values()), "no_split_id_family_scenario_collisions", collisions)
        report["split_collisions"] = collisions
        reviews = review_rows(ROOT / "dataset/review/v2_pilot/human_review_working.csv")+review_rows(ROOT / "dataset/review/v2_train_expansion/human_review_new8.csv")
        val_reviews = review_rows(ROOT / "dataset/review/v2_validation/human_review.csv")
        report["approval_gate"] = approval_audit(train, reviews)
        check(report["approval_gate"]["status"] == "BLOCKED" and report["approval_gate"]["eligible_for_normal_training"] == 0, "normal_training_fail_closed_current_208")
        report["review_csv_statuses"] = {split: {name: dict(Counter(r[f"검수_결과_{name}"] for r in rows)) for name in REVIEWERS}
            | {"final_agreement": dict(Counter(r["최종_합의_결과"] for r in rows))} for split, rows in (("train", reviews), ("validation", val_reviews))}
        hf = ROOT / "artifacts/v2_runtime_assets/hf"
        os.environ.update(HF_HOME=str(hf), HF_HUB_CACHE=str(hf/"hub"), HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", HF_HUB_DISABLE_TELEMETRY="1")
        sys.path.insert(0, str(REF))
        import torch
        import risk_speech_ai.dataset as runtime_dataset
        from risk_speech_ai.training_data import TrainingSample, build_training_samples
        from risk_speech_ai.train_cli import build_safe_training_samples
        from risk_speech_ai.dataset import RiskSpeechDataset, make_training_dataloader
        from risk_speech_ai.tokenization import load_koelectra_tokenizer, build_model_input
        from risk_speech_ai.labels import LABELS as RUNTIME_LABELS, to_multi_hot
        from risk_speech_ai.checkpoint import tokenizer_metadata, input_contract
        from risk_speech_ai.prepare_training_inputs import BACKEND_MASK_TOKENS
        manifest = read_json(REF / "source_manifest.json")
        check(Path(runtime_dataset.__file__).resolve().is_relative_to(REF.resolve())
              and all(sha(REF/e["path"]) == e["sha256"] for e in manifest["files"]), "pinned_PR35_code_integrity")
        check(tuple(RUNTIME_LABELS) == LABELS and Path(sys.prefix).resolve() == (ROOT/".venv-v2").resolve(), "venv_and_label_order")
        torch.set_num_threads(2)
        label_rows, text_rows = legacy_rows(train)
        safe, initial = build_safe_training_samples(label_rows, text_rows)
        check(len(safe.samples) == 136 and initial["excluded_unreviewed"] == 72
              and safe.statistics["missing_tuned_text"] == 72, "new72_exclusion_is_intended_status_gate")
        report["legacy_builder"] = dict(train_samples=len(safe.samples), initial=initial, safe=safe.statistics,
            authorization_flags_ignored=all(r["training_eligible"] is False for r in label_rows) and len(safe.samples)>0,
            warning="Legacy status filtering is not v2 two-person approval or split authorization; use the strict wrapper before any future training entry point.")
        try:
            prepare_partition(train, split="train", mode="training", sample_type=TrainingSample, to_multi_hot=to_multi_hot, reviews=reviews)
        except PipelineGateError:
            check(True, "training_mode_rejects_current_unapproved_data")
        else:
            check(False, "training_mode_rejects_current_unapproved_data")
        vl, vt = legacy_rows(val)
        vb = build_training_samples(vl, vt)
        check(not vb.samples and vb.statistics["excluded_unreviewed"] == 192, "all192_validation_unreviewed")
        mismatched_tokens = []
        import re
        for c in train+val:
            for u in c["utterances"]:
                unsupported = sorted(set(re.findall(r"\[[^\]]+\]", u["text"]))-BACKEND_MASK_TOKENS)
                if unsupported:
                    mismatched_tokens.append(dict(id=f"{c['synthetic_id']}-{u['utterance_id']}", tokens=unsupported))
        report["legacy_preparer_incompatibilities"] = dict(v2_ids_fail_PN_only_id_pattern=True,
            v2_guide_tokens_not_in_legacy_mask_set=mismatched_tokens,
            action="Do not run v2 through v1 historical prepare_team_approved; use v2 schema/masking plus review evidence gate.")
        tokenizer = load_koelectra_tokenizer(REVISION)
        repro = read_json(REF/"artifacts/risk_speech_ai/reports/reproducibility.json")
        check(tokenizer_metadata(tokenizer)["vocab_sha256"] == repro["tokenizer_vocab_sha256"], "pinned_real_tokenizer_fingerprint")
        runtime = torch, TrainingSample, to_multi_hot, RiskSpeechDataset, make_training_dataloader, build_model_input
        report["train_preflight"] = run_partition(train, "train", tokenizer, runtime)
        report["validation_preflight"] = run_partition(val, "validation", tokenizer, runtime)
        report["input_contract"] = input_contract()
        recovery = read_json(OUT/"v1_input_recovery.json")
        check(recovery["status"] == "RECOVERED_EXACT_SHA256" and all(sha(RECOVERED/f"{name}.jsonl") == row["expected_sha256"] for name,row in recovery["output"].items()), "actual_v1_recovered_input_hash_identity")
        v1_labels, v1_text = read_jsonl(RECOVERED/"labels.jsonl"), read_jsonl(RECOVERED/"tuned.jsonl")
        v1_built = build_training_samples(v1_labels, v1_text)
        check(len(v1_built.samples) == 1460, "recovered_v1_1460_samples")
        v1 = [dict(id=f"{r['conversation_id']}-{r['utterance_id']}", conversation_id=r["conversation_id"], text=r["tuned_text"], normalized=normalize(r["tuned_text"])) for r in v1_text]
        train_u, val_u = utterances(train), utterances(val)
        print("Auditing TRAIN/VALIDATION and actual v1 input overlap", flush=True)
        overlap = dict(normalization="NFKC + casefold; whitespace and Unicode punctuation removed",
            threshold=0.80, metric="SequenceMatcher(autojunk=False); exact upper bounds prune below threshold only",
            train_vs_validation=compare(train_u, val_u), v2_train_vs_actual_v1=compare(train_u, v1),
            v2_validation_vs_actual_v1=compare(val_u, v1), actual_v1_source_identity="RECOVERED_EXACT_SHA256",
            semantic_status="HUMAN_REVIEW_REQUIRED_LEXICAL_SCREEN_IS_NOT_SEMANTIC_PROOF",
            semantic_limit="No original v1 family manifest exists; do not infer semantic family independence from disjoint IDs or no >=0.80 text candidates.")
        write_json("independence_result.json", overlap)
        report["overlap_summary"] = {k: {field:v[field] for field in ("pairs_checked", "candidate_count", "kinds")}
            for k,v in overlap.items() if isinstance(v,dict) and "candidate_count" in v}
        report["v1_inputs"] = dict(status="READY_EXACT_HASH_RECOVERY", utterances=1460, conversations=68,
            files=recovery["output"], historical_split="NOT_FOUND_INDEPENDENT_SPLIT; PR35 explicitly records TRAIN IN-SAMPLE, independent validation/test false")
        report["v1_checkpoint"] = dict(status="NOT_FOUND", load_status="BLOCKED_FILE_MISSING", expected_sha256=repro["checkpoint"]["sha256"], expected_bytes=repro["checkpoint"]["bytes"])
        report["preservation_after"] = integrity()
        report["status"] = "READY_PREFLIGHT_BLOCKED_ACTUAL_TRAINING"
    except Exception as error:
        report.update(status="FAIL", exception=type(error).__name__, message=str(error), traceback=traceback.format_exc())
    report["check_counts"] = dict(passed=sum(r["passed"] for r in CHECKS), failed=sum(not r["passed"] for r in CHECKS))
    write_json("pipeline_result.json", report)
    print(json.dumps({k:v for k,v in report.items() if k not in ("checks", "approval_gate", "traceback")}, ensure_ascii=False, indent=2))
    if report["status"] == "FAIL":
        print(report["traceback"], file=sys.stderr)
    return int(report["status"] == "FAIL")


if __name__ == "__main__":
    raise SystemExit(main())
