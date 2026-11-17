"""Read-only parent restore and exclusive v3 checkpoint files."""
from __future__ import annotations

from copy import deepcopy
import importlib.util
from pathlib import Path
import gc
import os

from .common import (BUNDLE, BUNDLE_SHA, LABELS, PARENT_SHA, RUNS, REVISION,
                     bootstrap, digest, inside, read_json, require, sha)


def runtime():
    bootstrap()
    spec = importlib.util.spec_from_file_location('v3_parent_runtime', BUNDLE / 'stage5_runtime.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify_parent():
    require(sha(BUNDLE / 'bundle_manifest.json') == BUNDLE_SHA, 'Parent manifest SHA changed')
    m = read_json(BUNDLE / 'bundle_manifest.json')
    require(m['label_order'] == list(LABELS) and m['default_seed'] == 42 and m['epoch'] == 3 and
            m['candidate_arm'] == 'B_ratio' and m['thresholds'] == [.5]*9 and
            m['model_revision'] == m['tokenizer_revision'] == REVISION, 'Wrong parent contract')
    spec = m['models']['42']
    require(spec['path'] == 'models/B_ratio/seed_42.pt' and spec['sha256'] == PARENT_SHA, 'Wrong parent identity')
    path = inside(BUNDLE / spec['path'], BUNDLE)
    require(sha(path) == PARENT_SHA, 'Parent checkpoint SHA changed')
    return path, m


def load_v2_start():
    """Restore both heads/encoder, then clone storages away from mmap parent bytes."""
    import torch
    from transformers import AutoTokenizer
    path, manifest = verify_parent()
    module = runtime()
    tokenizer = AutoTokenizer.from_pretrained(str(BUNDLE / 'tokenizer'), local_files_only=True)
    model, metadata = module.load_model(path, PARENT_SHA, tokenizer, arm='B_ratio', seed=42,
                                        bindings=manifest['bindings'])
    # assign=True in v2 loader maps original weights. Explicit independent storages
    # avoid ever using parent-linked storage for optimizer updates.
    with torch.no_grad():
        for param in model.parameters():
            param.data = param.detach().clone()
    return model, tokenizer, deepcopy(metadata), manifest


def restore_state(model, state):
    """Same strict, all-parameter restore used in controlled tiny fixture tests."""
    model.load_state_dict(state, strict=True)
    return model


def save_v3_checkpoint(path, model, optimizer, *, metadata, lineage, epoch, history,
                       artifact_kind='research_model'):
    import torch
    path = inside(path, RUNS)
    require(path.suffix == '.pt', 'Checkpoint extension must be .pt')
    require(metadata.get('label_order') == list(LABELS), 'Checkpoint label order mismatch')
    require(epoch in (1, 2) and lineage.get('parent_sha256') == PARENT_SHA and
            lineage.get('optimizer_reset') is True, 'Checkpoint lineage invalid')
    require(artifact_kind in ('research_model', 'unit_test_fixture'), 'Unknown artifact kind')
    require(lineage.get('artifact_kind') == artifact_kind, 'Artifact kind mismatch')
    require(artifact_kind == 'unit_test_fixture' or lineage.get('training_authorized') is True,
            'Unapproved data cannot produce a research-model checkpoint')
    payload = dict(checkpoint_schema_version='v1', model_state_dict=model.state_dict(),
                   optimizer_state_dict=optimizer.state_dict(), epoch=epoch, label_order=list(LABELS),
                   metadata=deepcopy(metadata), base_model=metadata.get('base_model'),
                   training_config=deepcopy(metadata.get('training_config')),
                   v3_lite_metadata=dict(lineage, schema='v3-lite-checkpoint/1', epoch=epoch,
                       parent_label_status='provisional', inherited_unreviewed_synthetic_v2=True,
                       human_approved=False, deployment_approved=False, thresholds=[.5]*9),
                   epoch_losses=history)
    payload['step_count']=history[-1]['optimizer_steps'] if history else 0
    payload['sample_count']=history[-1]['samples'] if history else 0
    bootstrap()
    from risk_speech_ai.checkpoint import validate_checkpoint_metadata,validate_model_config
    validate_checkpoint_metadata(payload)
    validate_model_config(metadata,model)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(path)
    pending=path.with_suffix('.pt.partial')
    with pending.open('xb') as stream:
        torch.save(payload, stream)
        stream.flush(); os.fsync(stream.fileno())
    checked=torch.load(pending,map_location='cpu',weights_only=True,mmap=True)
    validate_checkpoint_metadata(checked)
    require(set(checked['model_state_dict'])==set(payload['model_state_dict']) and all(
        checked['model_state_dict'][k].shape==v.shape and checked['model_state_dict'][k].dtype==v.dtype
        for k,v in payload['model_state_dict'].items()),'Serialized tensor contract differs')
    del checked
    gc.collect()
    os.rename(pending,path)  # Windows refuses an existing destination; no overwrite.
    return dict(path=str(path), sha256=sha(path), bytes=path.stat().st_size,
                artifact_kind=artifact_kind, epoch=epoch)


def load_v3_state(path, model, expected_sha, *, tokenizer):
    import torch
    path = inside(path, RUNS)
    require(sha(path) == expected_sha, 'Saved v3 hash mismatch')
    p = torch.load(path, map_location='cpu', weights_only=True, mmap=True)
    require(p['label_order'] == list(LABELS) and p['v3_lite_metadata']['schema'] == 'v3-lite-checkpoint/1', 'Wrong v3 schema')
    bootstrap()
    from risk_speech_ai.checkpoint import validate_checkpoint_metadata,validate_model_config
    metadata=validate_checkpoint_metadata(p)
    validate_model_config(metadata,model)
    runtime().compatible_tokenizer(metadata,tokenizer)
    restore_state(model, p['model_state_dict'])
    model.eval()
    return p
