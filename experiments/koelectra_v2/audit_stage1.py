"""Read-only inventory; does not load weights, train, evaluate TEST or approve data."""
from __future__ import annotations

import csv
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'reports/v2_stage1_20261109'
LABELS = ['institution_impersonation', 'money_transfer', 'personal_information',
          'app_installation', 'secrecy', 'threat_pressure', 'loan_fraud', 'information_probing']


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def read(path):
    return json.loads((ROOT / path).read_text(encoding='utf-8'))


def rows(path):
    return [json.loads(line) for line in (ROOT / path).read_text(encoding='utf-8').splitlines() if line]


def inventory():
    sources = {
        'v1': 'artifacts/v1_recovered_8faa6a7eebfe/prepared/labels.jsonl',
        'train': 'dataset/04. processed/v2_train_expansion/train_24_mixed_review_candidate.jsonl',
        'aux_validation': 'dataset/04. processed/v2_validation/validation_24_generated.jsonl',
    }
    result = {}
    for role, path in sources.items():
        data = rows(path)
        utterances = data if role == 'v1' else [u for c in data for u in c['utterances']]
        positives = Counter(label for u in utterances for label in u['labels'])
        result[role] = dict(path=path, sha256=sha(ROOT / path),
                            conversations=len({r['conversation_id'] for r in data}) if role == 'v1' else len(data),
                            utterances=len(utterances), positives={k: positives[k] for k in LABELS})
        if role != 'v1':
            result[role]['families'] = sorted(c['scenario_family_id'] for c in data)
            result[role]['source_kinds'] = dict(Counter(c['source_kind'] for c in data))
    assert not set(result['train']['families']) & set(result['aux_validation']['families'])
    result['review_tables'] = {}
    for path in sorted((ROOT / 'dataset/review').rglob('*.csv')):
        records = list(csv.DictReader(path.open(encoding='utf-8-sig', newline='')))
        fields = [k for k in (records[0] if records else {}) if '검수_결과' in k or '최종_합의_결과' in k]
        result['review_tables'][path.relative_to(ROOT).as_posix()] = dict(
            sha256=sha(path), rows=len(records), decisions={k: dict(Counter(r[k] for r in records)) for k in fields})
    result['historical_public_assets'] = read('reports/v2_experiment_design/public_base_assets.json')
    # Old reports contain machine-specific paths. Verify presence here separately.
    local_roots = [ROOT / 'artifacts', ROOT.parents[1] / 'artifacts', ROOT.parents[1] / 'checkpoints',
                   ROOT.parents[1] / 'models', ROOT.parents[1] / '.venv-ai/hf-cache']
    assets = []
    for base in local_roots:
        if base.exists():
            for path in base.rglob('*'):
                if '.no_exist' not in path.parts and path.is_file() and (path.suffix in {'.pt', '.pth', '.safetensors'} or path.name == 'pytorch_model.bin'):
                    assets.append(dict(root=base.relative_to(ROOT.parents[1]).as_posix(),
                                       path=path.relative_to(base).as_posix(), bytes=path.stat().st_size, sha256=sha(path)))
    result['local_weight_inventory'] = assets
    result['scan_scope'] = 'worktree artifacts; primary workspace artifacts/checkpoints/models/.venv-ai/hf-cache only'
    result['local_revision'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    return result


def cpu_check():
    import os
    import sys
    cache = ROOT.parents[1] / '.venv-ai/hf-cache/hub'
    os.environ.update(HF_HUB_CACHE=str(cache), HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
    sys.path.insert(0, str(ROOT / 'artifacts/v1_reference/pr35_9bab7e383928'))
    sys.path.insert(0, str(ROOT / 'dataset/scripts'))
    import torch
    from transformers import ElectraTokenizer
    from risk_speech_ai.dataset import RiskSpeechDataset, make_training_dataloader
    from risk_speech_ai.training_data import TrainingSample
    from risk_speech_ai.labels import to_multi_hot
    from v2_pipeline_gate import prepare_partition
    snapshot = cache / 'models--monologg--koelectra-base-v3-discriminator/snapshots/68b30cd259f34a4b5aa8786392612ba2a2617fcc'
    tokenizer = ElectraTokenizer.from_pretrained(str(snapshot), local_files_only=True)
    require_hash = '9f50b0a44b0272dcf78bfd7a52a0815588f69918bb87ec60b21ca235c5aa0eb4'
    assert sha(snapshot / 'vocab.txt') == require_hash
    result = dict(training_executed=False, test_evaluated=False, checkpoint_loaded=False,
                  tokenizer_vocab_sha256=require_hash, partitions={})
    for role, file in [('train', 'v2_train_expansion/train_24_mixed_review_candidate.jsonl'),
                       ('validation', 'v2_validation/validation_24_generated.jsonl')]:
        data = rows('dataset/04. processed/' + file)
        prepared = prepare_partition(data, split=role, mode='preflight', sample_type=TrainingSample, to_multi_hot=to_multi_hot)
        assert not prepared.training_allowed
        loader = make_training_dataloader(RiskSpeechDataset(prepared.samples, tokenizer=tokenizer), tokenizer=tokenizer, batch_size=4, shuffle=False)
        count = batches = 0
        for batch in loader:
            n, width = batch['input_ids'].shape
            assert width <= 512 and all(t.device.type == 'cpu' for t in batch.values())
            assert batch['risk_target'].shape == (n, 1) and batch['type_targets'].shape == (n, 8)
            expected = prepared.samples[count:count+n]
            assert torch.equal(batch['risk_target'], torch.tensor([[s.risk_target] for s in expected], dtype=torch.float32))
            assert torch.equal(batch['type_targets'], torch.tensor([s.type_targets for s in expected], dtype=torch.float32))
            count += n
            batches += 1
        assert count == sum(len(c['utterances']) for c in data)
        result['partitions'][role] = dict(samples=count, batches=batches, training_allowed=False)
    return result


def capture():
    paths = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode('utf-8').split('\0')
    return {p: sha(ROOT / p) for p in paths if p and (ROOT / p).is_file()}


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['capture', 'verify', 'inventory', 'cpu'])
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if args.mode == 'capture':
        target, value = 'preservation_before.json', capture()
    elif args.mode == 'inventory':
        target, value = 'inventory.json', inventory()
    elif args.mode == 'cpu':
        target, value = 'cpu_preflight.json', cpu_check()
    else:
        before = read('reports/v2_stage1_20261109/preservation_before.json')
        changed = [p for p, digest in before.items() if not (ROOT / p).is_file() or sha(ROOT / p) != digest]
        target, value = 'preservation_result.json', dict(files=len(before), changed=changed, passed=not changed)
        if changed:
            raise SystemExit(f'Protected files changed: {changed}')
        assets = read('reports/v2_stage1_20261109/inventory.json')['local_weight_inventory']
        value['local_weight_files'] = len(assets)
        value['local_weights_unchanged'] = all(sha(ROOT.parents[1] / a['root'] / a['path']) == a['sha256'] for a in assets)
        if not value['local_weights_unchanged']:
            raise SystemExit('Local weights changed')
    (OUT / target).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(target, 'written')
