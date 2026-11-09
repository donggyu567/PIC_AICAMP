"""Validation-only, seed-mean epoch and nine-threshold selection."""
from __future__ import annotations

import math
import numpy as np

from expanded_common import LABELS, SEEDS, PROTOCOL_SHA, digest, require, write_json
from expanded_evaluation import probabilities, targets, validate_predictions, threshold_vector
from risk_speech_ai.metrics import binary_metrics

GRID = tuple(round(.1 + .05 * i, 2) for i in range(17))


def select_epoch(predictions, partition):
    partition.verify({'validation'})
    require(set(predictions) == {1, 2, 3}, 'Epochs 1,2,3 must all be present')
    y = targets(partition.rows)[:, 0]
    scores = {}
    for epoch, by_seed in predictions.items():
        require(set(by_seed) == set(SEEDS), 'All registered seeds required for epoch selection')
        values = []
        for seed, item in by_seed.items():
            validate_predictions(item, partition)
            require(item['seed'] == seed and item['epoch'] == epoch, 'Epoch/seed provenance differs')
            value = binary_metrics(y, probabilities(item['logits'])[:, 0], .5)['f1']
            require(value is not None, 'Validation has no positive risk support')
            values.append(value)
        scores[epoch] = float(np.mean(values))
    best = min(scores, key=lambda e: (-round(scores[e], 12), e))
    return dict(epoch=best, mean_seed_f1=scores, selection_role='validation')


def select_thresholds(by_seed, partition):
    partition.verify({'validation'})
    require(set(by_seed) == set(SEEDS), 'All registered seeds required for threshold selection')
    for seed, item in by_seed.items():
        validate_predictions(item, partition)
        require(item['seed'] == seed, 'Seed provenance mismatch')
    require(len({item['epoch'] for item in by_seed.values()}) == 1, 'Thresholds require the same selected epoch')
    y = targets(partition.rows)
    p = {seed: probabilities(item['logits']) for seed, item in by_seed.items()}
    values, support = [], []
    for index in range(9):
        positives = int(y[:, index].sum())
        negatives = len(y) - positives
        conversations = len({r['conversation_id'] for i, r in enumerate(partition.rows) if y[i, index]})
        eligible = positives >= 10 and negatives >= 10 and conversations >= 3
        if eligible:
            scores = {t: float(np.mean([binary_metrics(y[:, index], p[s][:, index], t)['f1'] for s in SEEDS])) for t in GRID}
            chosen = min(GRID, key=lambda t: (-round(scores[t], 12), round(abs(t-.5), 12), -t))
        else:
            chosen = .5
        values.append(chosen)
        support.append(dict(positive=positives, negative=negatives, positive_conversations=conversations,
                            tuned=eligible, reason=None if eligible else 'insufficient_validation_support'))
    return dict(values=values, support=support, output_order=['risk'] + list(LABELS))


def freeze_b(predictions, partition, weights, train_bindings, *, version, checkpoints):
    require(isinstance(version, str) and version and version != 'initial-0.5', 'New threshold version required')
    require(all(p['arm'] == 'B_ratio' for items in predictions.values() for p in items.values()), 'Only B_ratio can freeze C recipe')
    chosen = select_epoch(predictions, partition)
    thresholds = select_thresholds(predictions[chosen['epoch']], partition)
    bundle = dict(schema='expanded-frozen-B/1', protocol_sha256=PROTOCOL_SHA, version=version,
                  epoch=chosen['epoch'], weights=list(weights), thresholds=thresholds['values'],
                  threshold_support=thresholds['support'], label_order=list(LABELS), source='validation',
                  validation_bindings=partition.bindings, train_bindings=train_bindings,
                  checkpoint_references=checkpoints, epoch_scores=chosen['mean_seed_f1'])
    validate_frozen(bundle)
    return bundle


def validate_frozen(bundle):
    require(bundle.get('schema') == 'expanded-frozen-B/1' and bundle.get('protocol_sha256') == PROTOCOL_SHA,
            'Unknown B selection version/protocol')
    require(bundle['source'] == 'validation' and bundle['epoch'] in (1, 2, 3) and type(bundle['epoch']) is int,
            'Only validation may choose epoch/threshold')
    require(bundle['label_order'] == list(LABELS) and isinstance(bundle['version'], str) and bundle['version'], 'Selection labels/version mismatch')
    require(len(bundle['weights']) == 8 and all(type(w) in (int, float) and math.isfinite(w) and 1 <= w <= 10 for w in bundle['weights']), 'Invalid B weight vector')
    threshold_vector(bundle['thresholds'])
    require(set(bundle['checkpoint_references']) == {str(s) for s in SEEDS}, 'B checkpoint references must cover all seeds')
    for reference in bundle['checkpoint_references'].values():
        require(set(reference) == {'path', 'sha256'}, 'Invalid frozen checkpoint reference')
    for bindings in (bundle['validation_bindings'], bundle['train_bindings']):
        require(all(isinstance(bindings.get(k), str) and len(bindings[k]) == 64 for k in
                    ('data_sha256', 'split_sha256', 'approval_sha256', 'manifest_sha256')), 'Selection missing data/split/approval hash')
    require(bundle['validation_bindings']['split_sha256'] == bundle['train_bindings']['split_sha256'], 'Selection split mismatch')
    return bundle


def save_selection(path, bundle):
    validate_frozen(bundle)
    return write_json(path, bundle)


def validate_frozen_checkpoints(bundle, *, fixture=False):
    from pathlib import Path
    from expanded_common import OUTPUT
    from expanded_checkpoint import load_v2
    validate_frozen(bundle)
    for seed, reference in bundle['checkpoint_references'].items():
        path = Path(reference['path']).resolve()
        require(fixture or path.is_relative_to(OUTPUT.resolve()), 'B checkpoint must be in registered v2 namespace')
        loaded = load_v2(path, expected_sha256=reference['sha256'], fixture=fixture)
        meta = loaded['expanded_metadata']
        require(meta['arm'] == 'B_ratio' and meta['seed'] == int(seed) and meta['epoch'] == bundle['epoch'],
                'B selection checkpoint identity mismatch')
        require(meta['weights'] == bundle['weights'] and meta['bindings']['train'] == bundle['train_bindings'] and
                meta['bindings']['validation'] == bundle['validation_bindings'], 'B selection weights/data mismatch')
