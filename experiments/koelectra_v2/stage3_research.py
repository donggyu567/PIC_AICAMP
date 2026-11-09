"""Explicit research data adapter; never returns an authorized production Partition.

This module exposes TRAIN/VALIDATION samples, not a model trainer or TEST reader.
Phase 4 must explicitly select this research schema and record unreviewed labels.
"""
from dataclasses import dataclass
from pathlib import Path

from expanded_common import LABELS, checked_file, read, require, sha
from stage3_data import BASE, jsonl, validate
from risk_speech_ai.training_data import TrainingSample
from risk_speech_ai.labels import to_multi_hot


@dataclass(frozen=True)
class ResearchInput:
    role: str
    data_sha256: str
    manifest_sha256: str
    samples: tuple
    purpose: str = 'internal_experiment'
    label_status: str = 'provisional'
    human_review_complete: bool = False
    deployment_approved: bool = False


def causal_samples(conversations):
    return tuple(TrainingSample(c['conversation_id'], u['utterance_id'],
        [x['text'] for x in c['utterances'][max(0, i-5):i]], u['text'],
        float(u['is_phishing']), to_multi_hot(u['labels']))
        for c in conversations for i, u in enumerate(c['utterances']))


def load_research(role, *, mode, base=BASE):
    # Role/mode denial must precede any file IO, including a manifest read.
    require(role in ('train', 'validation'), 'Research development cannot access TEST')
    require(mode == 'internal_experiment', 'Explicit internal_experiment mode is required')
    base = Path(base).resolve()
    path = base/'data_use_manifest.json'
    manifest = read(path)
    require(manifest.get('schema') == 'internal-research-data/1', 'Wrong research schema')
    require(manifest['purpose'] == 'internal_experiment' and manifest['source_kind'] == 'llm_synthetic', 'Research provenance mismatch')
    require(manifest['human_review_complete'] is False and manifest['deployment_approved'] is False
            and manifest['production_training_authorized'] is False, 'Research input must not assert production approval')
    require(manifest['label_order'] == list(LABELS), 'Canonical label order mismatch')
    expected = {'train':'train_80_candidate.jsonl', 'validation':'validation_32_synthetic.jsonl'}[role]
    require(manifest[role]['path'] == expected, 'Unexpected research data reference')
    data = checked_file(base, manifest[role])
    conversations = jsonl(data)
    validate(conversations, expected=80 if role == 'train' else 32)
    require(all(c['split'] == role for c in conversations), 'Research role mixing')
    require(all(c.get('human_review_complete', False) is False for c in conversations), 'Unreviewed research view cannot assert human review')
    return ResearchInput(role, sha(data), sha(path), causal_samples(conversations))
