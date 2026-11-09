"""Exclusive atomic v2 snapshots, with the unchanged PR35 v1 envelope."""
from __future__ import annotations

import copy
import os
from pathlib import Path
import torch

from expanded_common import (ROOT, OUTPUT, ARMS, SEEDS, LABELS, REVISION, PROTOCOL_SHA,
                             digest, require, sha, publish, slug, write_json)
from risk_speech_ai.checkpoint import (validate_checkpoint_metadata, validate_model_config,
                                       validate_tokenizer, encoder_config)


def reconstruct_config(saved):
    """Restore an explicit null consumed by ElectraConfig.from_dict, without waiving PR35 validation."""
    from transformers import ElectraConfig
    config = ElectraConfig.from_dict(saved)
    if 'attn_implementation' in saved and saved['attn_implementation'] is None and 'attn_implementation' not in config.to_dict():
        config.attn_implementation = None
    return config


def materialize_buffers(model):
    """Rebuild only ELECTRA's nonpersistent position/zero segment buffers after meta loading."""
    for module in model.modules():
        for name, tensor in module._buffers.items():
            if tensor is not None and tensor.is_meta:
                require(name in ('position_ids', 'token_type_ids') and name in module._non_persistent_buffers_set,
                        'Unexpected nonserialized meta buffer')
                module._buffers[name] = (torch.arange(tensor.shape[-1], dtype=tensor.dtype).expand(tensor.shape).clone()
                                         if name == 'position_ids' else torch.zeros(tensor.shape, dtype=tensor.dtype))


def validate_extended(checkpoint, *, bindings=None, fixture=False):
    validate_checkpoint_metadata(checkpoint)
    ext = checkpoint.get('expanded_metadata', {})
    require(ext.get('schema') == 'expanded-checkpoint-extension/1', 'Missing v2 extension')
    require(ext.get('fixture') is fixture, 'Fixture/production checkpoint mismatch')
    require(ext['protocol_sha256'] == PROTOCOL_SHA and ext['label_order'] == list(LABELS), 'Protocol/label mismatch')
    require(ext['arm'] in ARMS and ext['seed'] in SEEDS, 'Unknown arm/seed')
    require(checkpoint['epoch'] == ext['epoch'] and checkpoint['step_count'] == ext['optimizer_steps'], 'Epoch/step metadata differs')
    require(checkpoint['metadata']['seed'] == ext['seed'], 'Seed differs from v1 envelope')
    require(ext['runtime_sha256'] == digest(ext['runtime']), 'Runtime metadata tampered')
    from expanded_common import validate_runtime
    validate_runtime(ext['runtime'])
    require(ext['runtime']['arm'] == ext['arm'] and ext['runtime']['seed'] == ext['seed'], 'Runtime arm/seed differs')
    require(checkpoint['metadata']['model_revision'] == REVISION and checkpoint['metadata']['tokenizer_revision'] == REVISION,
            'Model/tokenizer revision differs')
    for role in ('train', 'validation'):
        for field in ('data_sha256', 'split_sha256', 'approval_sha256', 'manifest_sha256'):
            require(isinstance(ext['bindings'][role].get(field), str) and len(ext['bindings'][role][field]) == 64, 'Missing bound hash')
    if bindings is not None:
        require(ext['bindings'] == bindings, 'Checkpoint data/split/approval hashes differ')
    require(type(ext['epoch']) is int and ext['epoch'] > 0 and type(ext['optimizer_steps']) is int and ext['optimizer_steps'] > 0, 'Invalid epoch/step')
    low, high = (0, 5) if ext['runtime']['weight_policy'] == 'sqrt5' else (1, 10)
    require(len(ext['weights']) == 8 and all(low <= x <= high for x in ext['weights']), 'Invalid weight vector')
    if ext['runtime']['weight_policy'] == 'none':
        require(ext['weights'] == [1.]*8, 'Unweighted arm contains positive weights')
    from expanded_evaluation import threshold_vector
    threshold_vector(ext['thresholds'])
    require(isinstance(ext['threshold_version'], str) and ext['threshold_version'], 'Threshold version absent')
    for state in checkpoint['optimizer_state_dict']['state'].values():
        require(float(state['step']) == ext['optimizer_steps'], 'Optimizer state not synchronized with model epoch')
    require(bool(checkpoint['optimizer_state_dict']['state']), 'Empty optimizer state')
    for state in [checkpoint['model_state_dict']] + list(checkpoint['optimizer_state_dict']['state'].values()):
        for tensor in state.values():
            if isinstance(tensor, torch.Tensor):
                require(torch.isfinite(tensor).all().item(), 'Non-finite checkpoint tensor')
    return ext


class RunStore:
    def __init__(self, arm, seed, run_id, *, fixture=False, root=OUTPUT):
        root = Path(root).absolute()
        require(arm in ARMS and seed in SEEDS, 'Invalid run arm/seed')
        if fixture:
            require(not root.resolve().is_relative_to(ROOT.resolve()), 'Fixture output must be temporary/outside repository')
        else:
            require(root == OUTPUT and root.resolve() == OUTPUT.absolute(), 'v2 output only; v1/symlink paths forbidden')
        self.path = root / slug(arm) / f'seed_{seed}' / slug(run_id)
        require(self.path.resolve().is_relative_to(root.resolve()), 'Run escapes output root')
        self.path.mkdir(parents=True, exist_ok=False)
        self.fixture = fixture

    def epoch(self, checkpoint):
        validate_extended(checkpoint, fixture=self.fixture)
        target = self.path / f"epoch_{checkpoint['epoch']:03d}.pt"
        publish(target, lambda stream: torch.save(checkpoint, stream))
        reference = dict(path=str(target), sha256=sha(target))
        write_json(target.with_suffix('.json'), dict(**reference, expanded_metadata=checkpoint['expanded_metadata']))
        return reference

    def alias(self, kind, reference):
        require(kind in ('best', 'last'), 'Unknown checkpoint alias')
        source = Path(reference['path'])
        require(source.parent == self.path and sha(source) == reference['sha256'], 'Alias source changed')
        target = self.path / f'{kind}.pt'
        os.link(source, target)  # immutable snapshot inode; never re-save historical weights
        write_json(self.path / f'{kind}.json', dict(epoch_checkpoint=reference, sha256=sha(target),
                   selection_scope='per_seed_validation_provisional' if kind == 'best' else 'last_epoch_or_step'))


def load_v2(path, *, expected_sha256, bindings=None, model=None, tokenizer=None, optimizer=None, fixture=False):
    require(sha(path) == expected_sha256, 'Checkpoint file hash mismatch')
    checkpoint = torch.load(path, map_location='cpu', weights_only=True, mmap=True)
    ext = validate_extended(checkpoint, bindings=bindings, fixture=fixture)
    if model is not None:
        require(tokenizer is not None, 'Tokenizer required for model load')
        validate_model_config(checkpoint['metadata'], model)
        validate_tokenizer(checkpoint['metadata'], tokenizer)
        expected = model.state_dict()
        require(set(expected) == set(checkpoint['model_state_dict']), 'Model state keys differ')
        require(all(expected[k].shape == v.shape for k, v in checkpoint['model_state_dict'].items()), 'State shape mismatch')
        # All contracts checked before touching caller state; test a disposable optimizer first.
        if optimizer is not None:
            temporary = copy.deepcopy(optimizer)
            temporary.load_state_dict(checkpoint['optimizer_state_dict'])
        model.load_state_dict(checkpoint['model_state_dict'], strict=True, assign=any(p.is_meta for p in model.parameters()))
        materialize_buffers(model)
        if optimizer is not None:
            optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
    return checkpoint


def model_for_inference(path, *, expected_sha256, tokenizer, bindings=None, fixture=False):
    from transformers import ElectraConfig, ElectraModel
    from risk_speech_ai.model import RiskSpeechClassifier
    checkpoint = load_v2(path, expected_sha256=expected_sha256, bindings=bindings, fixture=fixture)
    with torch.device('meta'):
        model = RiskSpeechClassifier(ElectraModel(reconstruct_config(checkpoint['metadata']['encoder_config'])))
    validate_model_config(checkpoint['metadata'], model)
    validate_tokenizer(checkpoint['metadata'], tokenizer)
    model.load_state_dict(checkpoint['model_state_dict'], strict=True, assign=True)
    materialize_buffers(model)
    return model.eval(), checkpoint
