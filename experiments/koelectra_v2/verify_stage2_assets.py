"""Read-only v1 verification and CPU smoke; no dataset performance evaluation."""
from __future__ import annotations

import argparse
import gc
import os
from pathlib import Path
import subprocess
import sys

from expanded_common import ROOT, MODEL, REVISION, require, sha, read, write_json

OUT = ROOT / 'reports/v2_stage2_20261109'
PRIMARY = ROOT.parents[1]
CACHE = PRIMARY / '.venv-ai/hf-cache/hub'
EXPECTED = '1131f9dcc665f79073d98ecd6845573109a89e44dbf2917d299a8fea057020a7'
FILES = [PRIMARY / 'artifacts/risk_speech_ai/koelectra_risk_v1.pt', PRIMARY / 'checkpoints/risk_speech_v1.pt']


def snapshot():
    paths = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode('utf-8').split('\0')
    return dict(tracked={p: sha(ROOT / p) for p in paths if p},
                weights={str(p): dict(bytes=p.stat().st_size, sha256=sha(p)) for p in FILES})


def verify_v1():
    os.environ.update(HF_HUB_CACHE=str(CACHE), HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
    import torch
    import transformers
    from transformers import ElectraConfig, ElectraModel
    from risk_speech_ai.checkpoint import validate_checkpoint_metadata, validate_model_config, validate_tokenizer, encoder_config
    from risk_speech_ai.model import RiskSpeechClassifier
    from risk_speech_ai.tokenization import load_koelectra_tokenizer
    from risk_speech_ai.inference import infer_batch, InferenceInput
    from expanded_checkpoint import reconstruct_config, materialize_buffers
    torch.set_num_threads(2)
    files = [dict(path=str(p), bytes=p.stat().st_size, sha256=sha(p)) for p in FILES]
    require(all(f['sha256'] == EXPECTED and f['bytes'] == 1348308730 for f in files), 'v1 hash/size differs')
    checkpoint = torch.load(FILES[0], map_location='cpu', weights_only=True, mmap=True)
    metadata = dict(validate_checkpoint_metadata(checkpoint))
    tokenizer = load_koelectra_tokenizer(REVISION)
    validate_tokenizer(metadata, tokenizer)
    # No random 450MB initialization/deep-copy; assign read-only mapped tensors to a meta model.
    with torch.device('meta'):
        model = RiskSpeechClassifier(ElectraModel(reconstruct_config(metadata['encoder_config'])))
    try:
        validate_model_config(metadata, model)
    except ValueError:
        current = encoder_config(model)
        difference = {k: dict(stored=metadata['encoder_config'].get(k), current=current.get(k))
                      for k in set(current) | set(metadata['encoder_config']) if current.get(k) != metadata['encoder_config'].get(k)}
        print('ENCODER_CONFIG_DIFFERENCE', difference, 'stored_only', set(metadata['encoder_config'])-set(current),
              'current_only', set(current)-set(metadata['encoder_config']), flush=True)
        raise
    model.load_state_dict(checkpoint['model_state_dict'], strict=True, assign=True)
    materialize_buffers(model)
    require(model.risk_classifier.out_features == 1 and model.type_classifier.out_features == 8, '1+8 head mismatch')
    output = infer_batch(model, [InferenceInput([], '안녕하세요. 오늘 날씨가 맑습니다.')], tokenizer=tokenizer, device='cpu')
    require(len(output) == 1 and len(output[0].type_probabilities) == 8, 'Smoke output mismatch')
    result = dict(status='PASS_SAFE_V1_LOAD_AND_INFERENCE', files=files, weights_only=True, mmap=True,
                  environment=dict(python=sys.version, torch=str(torch.__version__), transformers=transformers.__version__),
                  model_name=metadata['model_name'], model_revision=metadata['model_revision'],
                  tokenizer_compatible=True, encoder_config_compatible=True,
                  heads=[1, 8], original_v1_weights=True, smoke_inputs=1,
                  smoke_risk_probability=output[0].risk_probability,
                  smoke_type_probabilities=output[0].type_probabilities,
                  training_executed=False, performance_evaluation=False, test_predictions=False)
    del model, checkpoint
    gc.collect()
    return result


def verify_cpu():
    import torch
    from expanded_assets import fresh_public_model, load_tokenizer
    from expanded_cli import candidate_preflight
    from risk_speech_ai.tokenization import build_model_input
    from risk_speech_ai.inference import logits_to_outputs
    torch.set_num_threads(2)
    model, tok = fresh_public_model(42, CACHE), load_tokenizer(CACHE)
    prepared = build_model_input([], '가상 입력', tokenizer=tok)
    batch = {k: torch.tensor([getattr(prepared, k)], dtype=torch.long) for k in ('input_ids', 'attention_mask', 'token_type_ids')}
    model.eval()
    with torch.inference_mode():
        output = model(**batch)
    require(output.risk_logits.shape == (1, 1) and output.type_logits.shape == (1, 8), 'Public model head shape mismatch')
    logits_to_outputs(output)
    del model
    sys.path.insert(0, str(ROOT/'dataset/scripts'))
    from v2_pipeline_gate import approval_audit
    import csv
    source = ROOT/'dataset/04. processed/v2_train_expansion/train_24_mixed_review_candidate.jsonl'
    data = [__import__('json').loads(line) for line in source.read_text(encoding='utf-8').splitlines()]
    reviews = []
    for path in ['dataset/review/v2_pilot/human_review_working.csv', 'dataset/review/v2_train_expansion/human_review_new8.csv']:
        with (ROOT/path).open(encoding='utf-8-sig', newline='') as stream:
            reviews.extend(csv.DictReader(stream))
    gate = approval_audit(data, reviews)
    require(gate['status'] == 'BLOCKED' and gate['eligible_for_normal_training'] == 0, 'Real unapproved TRAIN gate unexpectedly opened')
    return dict(status='PASS_CPU_SMOKE_AND_BLOCKED_REAL_TRAIN_GATE', fresh_public_encoder_forward=[1, 1, 8],
                pretrained_encoder=True, fresh_seeded_heads=True, seed=42,
                preflight=[candidate_preflight(kind, CACHE) for kind in ('train', 'aux-validation')],
                real_train_gate={k: v for k, v in gate.items() if k != 'rows'},
                real_data_optimizer_updates=0, real_validation_selection=False, test_access=False)


def verify_second_copy():
    import torch
    from risk_speech_ai.checkpoint import validate_checkpoint_metadata
    path = FILES[1]
    require(sha(path) == EXPECTED, 'Second checkpoint hash differs')
    checkpoint = torch.load(path, map_location='cpu', weights_only=True, mmap=True)
    meta = validate_checkpoint_metadata(checkpoint)
    state = checkpoint['model_state_dict']
    require(tuple(state['risk_classifier.weight'].shape) == (1, 768) and
            tuple(state['type_classifier.weight'].shape) == (8, 768), 'Second checkpoint heads differ')
    return dict(status='PASS_SECOND_COPY_SAFE_CPU_LOAD', path=str(path), sha256=EXPECTED,
                bytes=path.stat().st_size, weights_only=True, mmap=True,
                metadata_validated=True, model_revision=meta['model_revision'], heads=[1, 8],
                identical_to_first_copy=True, training=False, saved=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['capture', 'verify-v1', 'verify-copy', 'cpu', 'preserve'])
    args = parser.parse_args()
    if args.mode == 'capture':
        write_json(OUT / 'assets_before.json', snapshot())
    elif args.mode == 'verify-v1':
        write_json(OUT / 'v1_checkpoint_smoke.json', verify_v1())
    elif args.mode == 'cpu':
        write_json(OUT / 'cpu_smoke.json', verify_cpu())
    elif args.mode == 'verify-copy':
        write_json(OUT / 'v1_second_copy.json', verify_second_copy())
    else:
        before = read(OUT / 'assets_before.json')
        changes = [p for p, value in before['tracked'].items() if sha(ROOT / p) != value]
        weights = [p for p, value in before['weights'].items() if sha(p) != value['sha256']]
        public_sha = sha(CACHE/f'models--monologg--koelectra-base-v3-discriminator/snapshots/{REVISION}/pytorch_model.bin')
        require(not changes and not weights and public_sha == 'f3f249cc07826bc2964a2c0dbbd0d239df4fe55efc03ba33e1bd1584cf56c566', 'Existing assets changed')
        write_json(OUT / 'preservation.json', dict(status='PASS', files=len(before['tracked']),
                   checkpoints=len(before['weights']), public_encoder_sha256=public_sha,
                   changed=changes, changed_checkpoints=weights))
    print(args.mode, 'PASS')
