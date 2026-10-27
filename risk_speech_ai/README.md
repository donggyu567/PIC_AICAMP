# Risk speech AI training and backend contract

Run from the repository root with `requirements-ai.txt` installed. The fixed
checkpoint path is `artifacts/risk_speech_ai/koelectra_risk_v1.pt`. It is a
schema v1 PyTorch dictionary containing trained model and optimizer states,
epoch, steps, losses, sample count, model/tokenizer identity, data version,
and the canonical eight-label order. `*.pt` is ignored by Git. The trained
checkpoint remains local and is **not included in this public repository or
PR**; obtain it only through an authorized private channel. Its recorded
SHA-256 is `1131f9dcc665f79073d98ecd6845573109a89e44dbf2917d299a8fea057020a7`.
The official server handoff uses a local copy at `checkpoints/risk_speech_v1.pt`;
see [CHECKPOINT_HANDOFF.md](CHECKPOINT_HANDOFF.md) for verified metadata,
the real loader entry point, and pending backend integration.

## Team-lead training-use decision (2026-10-26/27)

The project lead approved the management sheet's labeled data for model
training. This does not prove human review of each utterance. The adapter
writes `label_status=approved_for_training` and separately preserves the
sheet's conversation review display value as `human_review_status`. Every
label row records the source commit, path, row hash, and approval scope.
`provenance.json` records the same data version and policy. Source JSONL
and sheet cells are not edited.
`prepared/conversation_review_status_snapshot.json` separately records the
sheet's conversation display statuses for audit without changing the exact
label/tuned JSONL bytes used for this training run. These statuses are
conversation-level only.

The adapter checks the entire manifest, including conversations not marked
passed. It excludes N0015–N0019 for unconfirmed derivative-use permission,
sources outside `dataset/03. masked/`, unresolved phishing types, invalid
labels/IDs, unsupported mask tokens, and obvious unmasked personal IDs.
`pending.jsonl` records exclusions. Repeated text with consistent labels
may remain because its conversation context differs. Excluded utterances
cannot enter training history.

No saved backend LLM correction results were available. The adapter selects
`masked_text` when present, otherwise `text` from the masked source, then
checks mask tokens. The CLI-compatible `tuned_text` field is annotated with
`preprocessing=masked_source_text_no_llm_correction` and
`training_text_source` on each row. It has not been LLM tuned. Live inference
may use LLM-corrected text, so the input distributions can differ.

```powershell
$env:HF_HOME='.venv-ai/hf-cache'
$env:HF_HUB_OFFLINE='1'
.venv-ai\env\Scripts\python.exe -m risk_speech_ai.prepare_training_inputs --data-commit 8faa6a7eebfe95c7ac7fe6c6077a49ebf31f958f --approval-policy team_lead_training_use_20261026_27
.venv-ai\env\Scripts\python.exe -m risk_speech_ai.train_cli --labels-jsonl artifacts/risk_speech_ai/prepared/labels.jsonl --tuned-jsonl artifacts/risk_speech_ai/prepared/tuned.jsonl --data-version risk-speech-team_lead_training_use_20261026_27-8faa6a7eebfe --model-revision 68b30cd259f34a4b5aa8786392612ba2a2617fcc --tokenizer-revision 68b30cd259f34a4b5aa8786392612ba2a2617fcc --epochs 1 --batch-size 8 --learning-rate 2e-5 --seed 42 --device cpu
```

The second command is a validation-only dry run. Add `--train` only for a new,
authorized training job in an environment without an existing checkpoint. The
CLI refuses to overwrite the local trained checkpoint.
Defaults remain 3 epochs, batch size 8, learning rate 2e-5, seed 42; this
CPU run explicitly uses 1 epoch because no CUDA device is available.
Future `train_model()` calls create a unique log directory next to their
checkpoint. The CLI also accepts `--log-dir`. `batches.jsonl` stores actual
step losses, batch size, cumulative samples, learning rate, step duration,
and available working-set memory. `epochs.jsonl` stores weighted mean losses,
elapsed time, step count, and samples. Each line is flushed and synced before
the next step; write errors stop training. These logs did not exist for the
original v1 run. Its console observations and checkpoint epoch losses are
restored separately in `artifacts/risk_speech_ai/reports/training_history.csv`.

The earlier evidence policy remains available through
`--approval-policy utterance_evidence`, `--approvals-jsonl`, and
`--corrections-jsonl`. It requires actual utterance review and backend
correction evidence.

## Inference and backend integration

Restore with `load_checkpoint_inference(path, tokenizer=load_koelectra_tokenizer(revision))`.
Call `session.predict([InferenceInput(history_texts, current_text)])` with
up to five preceding included utterances as context. AI output retains
`risk_score` and `type_scores` in 0–100, `risk_probability` and
`type_probabilities` in 0–1, and `detected_types`. The backend `RiskAnalyzer`
adapter must pass the 0–1 probability fields directly, with no second
sigmoid or multiplication by 100.

## Evaluation and future independent splits

`python -m risk_speech_ai.evaluate_cli` evaluates the saved checkpoint on
the same 1,460 training utterances and writes aggregate results to
`artifacts/risk_speech_ai/reports/`. These are always **TRAIN (IN-SAMPLE)**
metrics, not validation or test results. The current checkpoint's hash is
checked before evaluation. No raw utterance text is written to reports.

For a future model, `splits.plan_conversation_splits()` groups whole
conversations connected by source item, identical text, and (by default)
source ID before seeded train/validation/test assignment. It records ratios,
seed, data version, and resulting counts, and fails if three nonempty
leak-free splits cannot be formed. Use validation data for model selection
and threshold choice, then evaluate the untouched test split once. The
existing 1,460 utterances have already trained v1 and cannot become its
independent test set by splitting them now.
