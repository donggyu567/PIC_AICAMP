#!/usr/bin/env python3
"""Audit generated validation and run the pinned, real CPU DataLoader offline.

No human review status is promoted, no training eligibility is assigned, and no
training/model/checkpoint API is called. Existing reviewed-only sample builders
correctly reject these unreviewed rows. The evaluation-only adapter constructs
the same TrainingSample type to test Dataset/DataLoader without false approval.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import traceback
import unicodedata
from collections import Counter
from datetime import datetime, timezone, timedelta
from difflib import SequenceMatcher
from itertools import combinations, product
from pathlib import Path

import prepare_pilot_review as review
from restore_pilot import CONVERSATION_FIELDS, UTTERANCE_FIELDS, LABELS
from validate_masked import ALLOWED_TOKENS, VALID_SPEAKERS

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "dataset/04. processed/v2_validation"
REPORTS = ROOT / "reports/v2_validation"
CANONICAL = DATA / "validation_24_generated.jsonl"
TRAIN = ROOT / "dataset/04. processed/v2_pilot/pilot_canonical.jsonl"
CANDIDATE = TRAIN.parent / "training_candidate/pilot_single_review_train_candidate.jsonl"
CSV = ROOT / "dataset/review/v2_validation/human_review.csv"
REFERENCE = ROOT / "artifacts/v1_reference/pr35_9bab7e383928"
REVISION = "68b30cd259f34a4b5aa8786392612ba2a2617fcc"
HF = ROOT / "artifacts/v2_runtime_assets/hf"
CHECKS = []


def require(condition, name, detail=None):
    CHECKS.append(dict(name=name, passed=bool(condition), detail=detail))
    if not condition:
        raise ValueError(name)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def no_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def jsonl(path):
    lines = path.read_text(encoding="utf-8").splitlines()
    require(bool(lines) and all(line.strip() for line in lines), f"nonblank_jsonl:{path.name}")
    rows = [json.loads(line, object_pairs_hook=no_duplicate_keys) for line in lines]
    require(all(isinstance(row, dict) for row in rows), f"json_objects:{path.name}")
    return rows


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def new_jsonl(path, rows):
    data = "".join(json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n" for r in rows).encode("utf-8")
    if path.exists():
        require(path.read_bytes() == data, f"preserve_existing_adapter:{path.name}")
    else:
        with path.open("xb") as stream:
            stream.write(data)


def normalize(value):
    return "".join(c for c in unicodedata.normalize("NFKC", value).casefold()
                   if not c.isspace() and not unicodedata.category(c).startswith("P"))


def flatten(conversations):
    return [dict(key=f"{c['synthetic_id']}-{u['utterance_id']}", text=u["text"],
                 normalized=normalize(u["text"])) for c in conversations for u in c["utterances"]]


def pair_audit(pairs):
    exact, normalized, near, screen = [], [], [], []
    highest = None
    for a, b in pairs:
        ratio = SequenceMatcher(None, a["normalized"], b["normalized"], autojunk=False).ratio()
        item = dict(left=a["key"], right=b["key"], similarity=round(ratio, 6),
                    left_text=a["text"], right_text=b["text"])
        if highest is None or ratio > highest["similarity"]:
            highest = item
        if a["text"] == b["text"]:
            exact.append(item)
        elif a["normalized"] == b["normalized"]:
            normalized.append(item)
        elif ratio >= .90:
            near.append(item)
        if ratio >= .80:
            screen.append(item)
    return dict(exact=exact, normalized_only=normalized, near_at_090=near,
                screening_at_080=screen, highest_similarity_pair=highest)


def validate_structure(conversations, train, registry):
    require(len(conversations) == 24, "exactly_24_conversations")
    require(len(train) == 16, "baseline_train_16")
    require([{k: v for k, v in c.items() if k != "review_preparation"} for c in jsonl(CANDIDATE)] == train,
            "train_candidate_and_canonical_match")
    ids, keys, families, scenarios = [], [], [], []
    field_reference = set(train[0])
    counts = Counter()
    normal = 0
    for index, c in enumerate(conversations, 1):
        cid = c["synthetic_id"]
        ids.append(cid)
        families.append(c["scenario_family_id"])
        scenarios.append(c["scenario_id"])
        require(set(c) == field_reference and CONVERSATION_FIELDS <= set(c), f"actual_canonical_fields:{cid}")
        require(cid == f"SYN2-VALIDATION-{index:04}", f"validation_namespace:{cid}")
        require(c["split"] == "validation" and c["is_synthetic"] is True and c["actual_call"] is False
                and c["source_kind"] == "llm_simulation" and c["review_status"] == "generated",
                f"split_synthetic_unreviewed:{cid}")
        require(c["variant_id"] == "original" and c["split_version"] == c["prompt_version"] == "v2-validation-24-1",
                f"generation_versions:{cid}")
        require(c["generation_model"] == registry["generation"]["model"] and bool(c["revision_history"])
                and all(r["human_approved"] is False and r["revision_model"] == c["generation_model"] for r in c["revision_history"]),
                f"generation_history_not_human_approved:{cid}")
        require(8 <= len(c["utterances"]) <= 10, f"utterances_8_to_10:{cid}")
        require(c["primary_type"] is None or c["primary_type"] in LABELS, f"primary_type:{cid}")
        require(isinstance(c["scenario_summary"], str) and bool(c["scenario_summary"].strip())
                and isinstance(c["review_flags"], list) and bool(c["review_flags"]), f"scenario_and_flags:{cid}")
        for position, u in enumerate(c["utterances"], 1):
            uid = f"{cid}-{position}"
            keys.append(uid)
            require(set(u) == UTTERANCE_FIELDS and type(u["utterance_id"]) is int
                    and u["utterance_id"] == position and u["speaker"] in VALID_SPEAKERS, f"utterance_fields_order_speaker:{uid}")
            require(isinstance(u["text"], str) and bool(u["text"].strip())
                    and isinstance(u["label_rationale"], str) and bool(u["label_rationale"].strip()), f"text_and_rationale:{uid}")
            require(isinstance(u["labels"], list) and len(u["labels"]) == len(set(u["labels"]))
                    and all(label in LABELS for label in u["labels"]) and type(u["is_phishing"]) is bool,
                    f"allowed_labels_and_boolean:{uid}")
            # This corpus has no out-of-taxonomy positives. Guide v3.2 permits
            # those only with an explicit review queue; do not silently force a label.
            require(u["is_phishing"] == bool(u["labels"]), f"no_phishing_label_contradiction:{uid}")
            tokens = re.findall(r"\[([^\]]+)\]", u["text"])
            require(set(tokens) <= ALLOWED_TOKENS and "raw_text" not in u and "masked_text" not in u,
                    f"masking_tokens:{uid}")
            require(not re.search(r"(?:\d[ -]?){7,}|https?://|[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}", u["text"]),
                    f"no_numeric_identifiers_urls_or_literal_email:{uid}")
            counts.update(u["labels"])
        positives = [u for u in c["utterances"] if u["is_phishing"]]
        normal += not positives
        require((c["primary_type"] is None) == (not positives)
                and (not positives or c["primary_type"] in {l for u in positives for l in u["labels"]}),
                f"normal_or_primary_matches_utterances:{cid}")
    require(len(set(ids)) == 24 and len(set(keys)) == len(keys) and len(set(families)) == 24
            and len(set(scenarios)) == 24, "unique_conversation_composite_utterance_family_scenario_ids")
    # utterance_id is intentionally conversation-local, as in the existing TRAIN.
    require(all(counts[label] > 0 for label in LABELS) and normal > 0, "all_eight_labels_and_entirely_normal_conversations")
    require(registry["reserved_split"] == "validation" and registry["block_future_train_reuse"] is True,
            "registry_blocks_future_train_reuse")
    designs = registry["scenarios"]
    require(len(designs) == 24 and {d["synthetic_id"] for d in designs} == set(ids), "design_coverage")
    for c, d in zip(conversations, designs):
        require(all(c[k] == d[k] for k in ("synthetic_id", "scenario_family_id", "scenario_id", "primary_type"))
                and d["reuse_in_future_train"] is False and d["reserved_split"] == "validation"
                and d["is_entirely_normal"] == (c["primary_type"] is None)
                and d["observed_labels"] == [label for label in LABELS if any(label in u["labels"] for u in c["utterances"])],
                f"design_matches_canonical:{c['synthetic_id']}")
    for relative, digest in registry["generation"]["input_sha256"].items():
        require(sha(ROOT / relative) == digest, f"generation_input_integrity:{relative}")
    return dict(conversations=len(conversations), utterances=len(keys),
                phishing=sum(u["is_phishing"] for c in conversations for u in c["utterances"]),
                normal_utterances=sum(not u["is_phishing"] for c in conversations for u in c["utterances"]),
                entirely_normal_conversations=normal, phishing_conversations=24-normal,
                positive_labels={label: counts[label] for label in LABELS},
                label_positive_conversations={label: sum(any(label in u["labels"] for u in c["utterances"]) for c in conversations) for label in LABELS},
                multi_label_utterances=sum(len(u["labels"]) > 1 for c in conversations for u in c["utterances"]))


def validate_csv(conversations):
    require(CSV.read_bytes().startswith(b"\xef\xbb\xbf"), "csv_utf8_bom")
    with CSV.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        require(reader.fieldnames == review.COLUMNS, "reuse_exact_train_review_columns")
        rows = list(reader)
    from generate_v2_validation import expected_review_rows
    expected = expected_review_rows(conversations)
    require(rows == expected, "all_review_rows_match_source_and_start_unapproved")
    require(len(rows) == sum(len(c["utterances"]) for c in conversations), "csv_complete_utterance_coverage")
    return dict(rows=len(rows), reviewers={name: dict(Counter(r[f"검수_결과_{name}"] for r in rows)) for name in review.REVIEWERS},
                final_agreement=dict(Counter(r["최종_합의_결과"] for r in rows)), training_applied=False)


def independence(conversations, train):
    val, tr = flatten(conversations), flatten(train)
    train_pairs = pair_audit(product(val, tr))
    within = pair_audit(combinations(val, 2))
    transcript = lambda c: dict(key=c["synthetic_id"], text="\n".join(u["text"] for u in c["utterances"]),
                                normalized=normalize("\n".join(u["text"] for u in c["utterances"])))
    transcripts = pair_audit(product(map(transcript, conversations), map(transcript, train)))
    existing_ids, existing_families, existing_scenarios, test_files = set(), set(), set(), []
    scanned = []
    for path in sorted((ROOT / "dataset/04. processed").rglob("*.jsonl")):
        if DATA in path.parents:
            continue
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
        scanned.append(dict(path=path.relative_to(ROOT).as_posix(), sha256=sha(path), rows=len(rows)))
        if any(r.get("split") == "test" for r in rows):
            test_files.append(path.relative_to(ROOT).as_posix())
        for c in rows:
            existing_ids.update(filter(None, (c.get("synthetic_id"), c.get("conversation_id"))))
            if c.get("scenario_family_id"):
                existing_families.add(c["scenario_family_id"])
            if c.get("scenario_id"):
                existing_scenarios.add(c["scenario_id"])
    id_collisions = sorted({c["synthetic_id"] for c in conversations} & existing_ids)
    family_collisions = sorted({c["scenario_family_id"] for c in conversations} & existing_families)
    scenario_collisions = sorted({c["scenario_id"] for c in conversations} & existing_scenarios)
    result = dict(normalization="NFKC + casefold; remove whitespace and Unicode punctuation",
                  similarity="difflib.SequenceMatcher(autojunk=False); high >= 0.90; extra screen >= 0.80",
                  train_source_sha256=sha(TRAIN), candidate_source_sha256=sha(CANDIDATE),
                  train_utterance_pairs=len(val)*len(tr), within_validation_pairs=len(val)*(len(val)-1)//2,
                  train_utterances=train_pairs, within_validation=within, train_full_transcripts=transcripts,
                  id_collisions=id_collisions, family_collisions=family_collisions, scenario_collisions=scenario_collisions,
                  existing_processed_files_scanned=scanned, local_test_files_found=test_files,
                  test_status="NO_INDEPENDENT_TEST_INPUT_SUPPLIED" if not test_files else "LOCAL_TEST_IDS_SCANNED_ONLY",
                  actual_v1_training_duplicate_status="NOT_VERIFIED_INPUTS_UNAVAILABLE",
                  semantic_independence="GENERATOR_DESIGN_COMPARISON_ONLY_HUMAN_REVIEW_PENDING",
                  semantic_limitation="Lexical similarity cannot prove absence of paraphrases or equivalent fraud scripts. See scenario_design.md and review all 24 against TRAIN.")
    write_json(REPORTS / "duplicate_report.json", result)
    require(not id_collisions and not family_collisions and not scenario_collisions, "no_existing_id_family_scenario_collision")
    for name, value in (("train_utterances", train_pairs), ("within_validation", within), ("train_transcripts", transcripts)):
        require(not value["exact"] and not value["normalized_only"] and not value["near_at_090"], f"no_exact_normalized_or_090_duplicate:{name}")
    return result


def evaluation_samples(conversations, sample_type, to_multi_hot):
    """Validation-only labels stay generated/unreviewed; no reviewed fiction."""
    samples, label_rows, text_rows, exported = [], [], [], []
    for c in conversations:
        if c["split"] != "validation" or c["review_status"] != "generated":
            raise ValueError("Evaluation adapter accepts generated validation only")
        for offset, u in enumerate(c["utterances"]):
            history = [previous["text"] for previous in c["utterances"][max(0, offset-5):offset]]
            sample = sample_type(c["synthetic_id"], u["utterance_id"], history, u["text"],
                                 float(u["is_phishing"]), to_multi_hot(u["labels"]))
            samples.append(sample)
            common = dict(conversation_id=c["synthetic_id"], utterance_id=u["utterance_id"], split="validation",
                          is_synthetic=True, actual_call=False, scenario_family_id=c["scenario_family_id"],
                          review_status="generated", final_approved=False, evaluation_only=True, training_eligible=False)
            label_rows.append({**common, "label_status": "unreviewed", "is_phishing": u["is_phishing"], "labels": u["labels"]})
            text_rows.append({**common, "tuned_text": u["text"], "text_transform": "identity_from_canonical"})
            exported.append({**common, "history_utterance_ids": list(range(max(1, u["utterance_id"]-5), u["utterance_id"]))})
    return samples, label_rows, text_rows, exported


def real_minibatch(conversations):
    os.environ.update(HF_HOME=str(HF), HF_HUB_CACHE=str(HF / "hub"), HF_HUB_OFFLINE="1",
                      TRANSFORMERS_OFFLINE="1", HF_HUB_DISABLE_TELEMETRY="1")
    sys.path.insert(0, str(REFERENCE))
    import torch
    import transformers
    import risk_speech_ai.dataset as dataset_module
    from risk_speech_ai.dataset import RiskSpeechDataset, make_training_dataloader
    from risk_speech_ai.training_data import TrainingSample, build_training_samples
    from risk_speech_ai.labels import LABELS as RUNTIME_LABELS, to_multi_hot
    from risk_speech_ai.tokenization import load_koelectra_tokenizer, build_model_input
    from risk_speech_ai.checkpoint import tokenizer_metadata

    manifest = read_json(REFERENCE / "source_manifest.json")
    require(Path(dataset_module.__file__).resolve().is_relative_to(REFERENCE.resolve())
            and all(sha(REFERENCE / e["path"]) == e["sha256"] for e in manifest["files"]), "pinned_PR35_runtime_code_integrity")
    require(Path(sys.prefix).resolve() == (ROOT / ".venv-v2").resolve() and sys.prefix != sys.base_prefix, "reuse_isolated_venv_v2")
    require(tuple(RUNTIME_LABELS) == LABELS, "runtime_label_order_matches")
    torch.set_num_threads(2)
    samples, labels, texts, history = evaluation_samples(conversations, TrainingSample, to_multi_hot)
    sources = {(c["synthetic_id"], u["utterance_id"]): c for c in conversations for u in c["utterances"]}
    rejected = build_training_samples(labels, texts)
    require(len(rejected.samples) == 0 and rejected.statistics["excluded_unreviewed"] == len(samples),
            "existing_training_builder_rejects_all_unreviewed_validation", rejected.statistics)
    # Save only unreviewed non-training inputs, never fabricate reviewed status.
    new_jsonl(DATA / "evaluation_label_candidates.jsonl", labels)
    new_jsonl(DATA / "evaluation_text_candidates.jsonl", texts)
    new_jsonl(DATA / "context_audit.jsonl", history)
    tokenizer = load_koelectra_tokenizer(REVISION)
    token_meta = tokenizer_metadata(tokenizer)
    expected_vocab = read_json(REFERENCE / "artifacts/risk_speech_ai/reports/reproducibility.json")["tokenizer_vocab_sha256"]
    require(token_meta["vocab_sha256"] == expected_vocab, "pinned_tokenizer_fingerprint")
    prepared = [build_model_input(s.history_texts, s.current_text, tokenizer=tokenizer) for s in samples]
    dataset = RiskSpeechDataset(samples, tokenizer=tokenizer)
    loader = make_training_dataloader(dataset, tokenizer=tokenizer, batch_size=4, shuffle=False)
    require(isinstance(loader, torch.utils.data.DataLoader) and len(dataset) == len(samples), "real_torch_DataLoader_and_dataset")
    offset, batch_count, first_shapes = 0, 0, None
    for batch in loader:
        batch_count += 1
        n, width = batch["input_ids"].shape
        require(0 < n <= 4 and width <= 512 and all(v.device.type == "cpu" for v in batch.values()), f"cpu_batch_size_and_length:{batch_count}")
        for key in ("input_ids", "attention_mask", "token_type_ids"):
            require(batch[key].dtype == torch.int64 and tuple(batch[key].shape) == (n, width), f"input_shape_dtype:{batch_count}:{key}")
        require(tuple(batch["risk_target"].shape) == (n, 1) and batch["risk_target"].dtype == torch.float32
                and tuple(batch["type_targets"].shape) == (n, 8) and batch["type_targets"].dtype == torch.float32, f"target_shape_dtype:{batch_count}")
        expected_risk = torch.tensor([[s.risk_target] for s in samples[offset:offset+n]], dtype=torch.float32)
        expected_types = torch.tensor([s.type_targets for s in samples[offset:offset+n]], dtype=torch.float32)
        require(torch.equal(batch["risk_target"], expected_risk) and torch.equal(batch["type_targets"], expected_types), f"target_values:{batch_count}")
        for row, item in enumerate(prepared[offset:offset+n]):
            length = item.token_count
            for key in ("input_ids", "attention_mask", "token_type_ids"):
                require(batch[key][row, :length].tolist() == getattr(item, key), f"real_token_values:{offset+row}:{key}")
            require(not batch["attention_mask"][row, length:].any()
                    and all(v == tokenizer.pad_token_id for v in batch["input_ids"][row, length:].tolist())
                    and not batch["token_type_ids"][row, length:].any(), f"padding_values:{offset+row}")
            s = samples[offset+row]
            c = sources[s.conversation_id, s.utterance_id]
            require(c["synthetic_id"] == s.conversation_id and s.current_text == c["utterances"][s.utterance_id-1]["text"]
                    and s.history_texts == [u["text"] for u in c["utterances"][max(0, s.utterance_id-6):s.utterance_id-1]]
                    and s.risk_target == float(c["utterances"][s.utterance_id-1]["is_phishing"])
                    and s.type_targets == to_multi_hot(c["utterances"][s.utterance_id-1]["labels"]), f"source_context_and_target_identity:{offset+row}")
        if first_shapes is None:
            first_shapes = {key: dict(shape=list(v.shape), dtype=str(v.dtype), device=str(v.device)) for key, v in batch.items()}
        offset += n
    require(offset == len(samples) == 192 and batch_count == 48, "all_192_samples_in_48_real_cpu_batches")
    return dict(status="PASS_REAL_CPU_DATALOADER_EVALUATION_ONLY", samples=len(samples), batches=batch_count, batch_size=4,
                first_batch=first_shapes, token_length_min=min(p.token_count for p in prepared), token_length_max=max(p.token_count for p in prepared),
                max_history=max(len(s.history_texts) for s in samples), context_targets_verified=offset,
                dropped_history=sum(p.dropped_history_count for p in prepared), tokenizer_revision=REVISION, tokenizer_metadata=token_meta,
                runtime_revision=manifest["revision"], training_builder_exclusion_statistics=rejected.statistics,
                adapter_policy="Construct existing TrainingSample for evaluation only; keep on-disk label_status=unreviewed. No approval override or training CLI.",
                environment=dict(python=sys.version, executable=sys.executable, torch=torch.__version__, transformers=transformers.__version__, platform=platform.platform()))


def preservation():
    baseline = read_json(REPORTS / "protected_baseline.json")
    changed = [relative for relative, digest in baseline["files"].items() if not (ROOT / relative).is_file() or sha(ROOT / relative) != digest]
    require(not changed, "all_preexisting_data_reviews_runtime_inputs_unchanged", dict(files=len(baseline["files"]), changed=changed))
    require(subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip() == baseline["head"]
            and subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT, text=True).strip() == baseline["branch"], "git_head_and_branch_unchanged")
    return dict(files=len(baseline["files"]), changed=changed, original_head=baseline["head"], original_branch=baseline["branch"])


def main():
    report = dict(status="RUNNING", checked_at=datetime.now(timezone(timedelta(hours=9))).isoformat(), checks=CHECKS,
                  training_executed=False, model_loaded=False, checkpoint_written=False, optimization_performed=False,
                  human_approval_assigned=False, actual_v1_duplicate_check="NOT_VERIFIED_INPUTS_UNAVAILABLE")
    try:
        report["preservation_before"] = preservation()
        conversations, train = jsonl(CANONICAL), jsonl(TRAIN)
        registry = read_json(DATA / "scenario_registry.json")
        report["statistics"] = validate_structure(conversations, train, registry)
        report["review_csv"] = validate_csv(conversations)
        duplicates = independence(conversations, train)
        report["duplicates"] = {k: {name: len(value[name]) for name in ("exact", "normalized_only", "near_at_090", "screening_at_080")}
                                for k, value in duplicates.items() if k in ("train_utterances", "within_validation", "train_full_transcripts")}
        report["scenario_family_collisions"] = duplicates["family_collisions"]
        report["minibatch"] = real_minibatch(conversations)
        report["preservation_after"] = preservation()
        report["output_sha256"] = {p.relative_to(ROOT).as_posix(): sha(p) for p in [CANONICAL, DATA / "scenario_registry.json", CSV]}
        report["status"] = "PASS_AUTOMATION_HUMAN_REVIEW_PENDING"
    except Exception as error:
        report.update(status="FAIL", exception=type(error).__name__, message=str(error), traceback=traceback.format_exc())
    report["check_counts"] = dict(passed=sum(c["passed"] for c in CHECKS), failed=sum(not c["passed"] for c in CHECKS))
    write_json(REPORTS / "validation_result.json", report)
    print(json.dumps({k: v for k, v in report.items() if k not in ("checks", "traceback", "output_sha256")}, ensure_ascii=False, indent=2))
    if report["status"] == "FAIL":
        print(report["traceback"], file=sys.stderr)
    return int(report["status"] == "FAIL")


if __name__ == "__main__":
    raise SystemExit(main())
