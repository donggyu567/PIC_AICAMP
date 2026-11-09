"""PR35-based metrics and role-gated inference; no TEST selection path."""
from __future__ import annotations

from collections import defaultdict
import math
import numpy as np
import torch

from expanded_common import LABELS, SEEDS, require, digest
from risk_speech_ai.metrics import binary_metrics
from risk_speech_ai.inference import logits_to_outputs
from risk_speech_ai.model import ModelOutput
from risk_speech_ai.dataset import RiskSpeechDataset, make_training_dataloader


def threshold_vector(values):
    require(len(values) == 9 and all(type(x) in (int, float) and math.isfinite(x) and 0 <= x <= 1 for x in values),
            'Exactly nine finite thresholds in risk + canonical type order required')
    return np.asarray(values, dtype=float)


def probabilities(logits):
    values = np.asarray(logits, dtype=float)
    require(values.ndim == 2 and values.shape[1] == 9 and len(values) > 0 and np.isfinite(values).all(), 'Finite [N,9] logits required')
    # Reuse the actual inference conversion; sigmoid exactly once, never on supplied probabilities.
    output = ModelOutput(torch.tensor(values[:, :1], dtype=torch.float64),
                         torch.tensor(values[:, 1:], dtype=torch.float64))
    converted = logits_to_outputs(output)
    return np.asarray([[r.risk_probability] + [r.type_probabilities[k] for k in LABELS] for r in converted])


def targets(rows):
    return np.asarray([[int(r['is_phishing'])] + [int(label in r['labels']) for label in LABELS] for r in rows])


def score_binary(y, p, threshold):
    result = binary_metrics(y, p, float(threshold))
    result['fpr'] = result['fp'] / result['negative'] if result['negative'] else None
    result['fnr'] = result['fn'] / result['positive'] if result['positive'] else None
    if result['fpr'] is None:
        result['undefined_reasons']['fpr'] = 'no_actual_negative'
    if result['fnr'] is None:
        result['undefined_reasons']['fnr'] = 'no_actual_positive'
    return result


def evaluate_logits(rows, logits, thresholds=(.5,) * 9):
    p, t, y = probabilities(logits), threshold_vector(thresholds), targets(rows)
    require(y.shape == p.shape, 'Prediction/target alignment mismatch')
    predicted = p >= t
    per_type = {}
    for index, label in enumerate(LABELS, 1):
        item = score_binary(y[:, index], p[:, index], t[index])
        item['families'] = len({r['scenario_family_id'] for r in rows})
        item['positive_families'] = len({r['scenario_family_id'] for r in rows if label in r['labels']})
        item['positive_conversations'] = len({r['conversation_id'] for r in rows if label in r['labels']})
        per_type[label] = item
    tp = sum(x['tp'] for x in per_type.values())
    fp = sum(x['fp'] for x in per_type.values())
    fn = sum(x['fn'] for x in per_type.values())
    defined = [item['f1'] for item in per_type.values() if item['f1'] is not None]
    conversations = defaultdict(list)
    for index, row in enumerate(rows):
        conversations[row['conversation_id']].append(index)
    normal = [ids for ids in conversations.values() if not y[ids, 0].any()]
    risky = [ids for ids in conversations.values() if y[ids, 0].any()]
    hn = [i for i, row in enumerate(rows) if row['hard_negative']]
    grouped = {}
    for field in ('source_id', 'scenario_family_id'):
        grouped[field] = {}
        for value in sorted({r[field] for r in rows}):
            ids = [i for i, r in enumerate(rows) if r[field] == value]
            grouped[field][value] = score_binary(y[ids, 0], p[ids, 0], t[0])
    return dict(binary=score_binary(y[:, 0], p[:, 0], t[0]), per_type=per_type,
                micro=dict(precision=tp/(tp+fp) if tp+fp else None,
                           recall=tp/(tp+fn) if tp+fn else None,
                           f1=2*tp/(2*tp+fp+fn) if tp+fn else None, tp=tp, fp=fp, fn=fn),
                macro=dict(f1=float(np.mean(defined)) if defined else None,
                           defined_labels=len(defined), full8_f1=float(np.mean(defined)) if len(defined) == 8 else None),
                hard_negative=dict(n=len(hn), fp=int(predicted[hn, 0].sum()),
                                   fpr=float(predicted[hn, 0].mean()) if hn else None),
                conversations=dict(normal=len(normal), normal_false_alerts=sum(bool(predicted[ids, 0].any()) for ids in normal),
                    normal_false_alert_rate=sum(bool(predicted[ids, 0].any()) for ids in normal)/len(normal) if normal else None,
                    risky=len(risky), risky_missed=sum(not predicted[ids, 0].any() for ids in risky),
                    risky_miss_rate=sum(not predicted[ids, 0].any() for ids in risky)/len(risky) if risky else None),
                groups=grouped,
                errors=[dict(conversation_id=r['conversation_id'], utterance_id=r['utterance_id'],
                             risk_fp=bool(predicted[i, 0] and not y[i, 0]),
                             risk_fn=bool(not predicted[i, 0] and y[i, 0]),
                             type_fp=[label for j, label in enumerate(LABELS, 1) if predicted[i, j] and not y[i, j]],
                             type_fn=[label for j, label in enumerate(LABELS, 1) if not predicted[i, j] and y[i, j]])
                        for i, r in enumerate(rows) if (predicted[i] != y[i]).any()])


def infer_partition(model, tokenizer, partition, *, seed, epoch, arm):
    partition.verify({'validation', 'test'})
    samples = partition.samples()
    loader = make_training_dataloader(RiskSpeechDataset(samples, tokenizer=tokenizer), tokenizer=tokenizer,
                                      batch_size=8, shuffle=False)
    before = model.training
    values = []
    try:
        model.eval()
        with torch.inference_mode():
            for batch in loader:
                output = model(**{k: batch[k] for k in ('input_ids', 'attention_mask', 'token_type_ids')})
                values.extend(torch.cat([output.risk_logits, output.type_logits], dim=1).cpu().tolist())
    finally:
        model.train(before)
    probabilities(values)  # shapes and non-finite check, no selection
    return dict(schema='expanded-predictions/1', role=partition.role, seed=seed, epoch=epoch, arm=arm,
                bindings=partition.bindings, row_keys=[f'{s.conversation_id}:{s.utterance_id}' for s in samples],
                logits=values)


def validate_predictions(prediction, partition):
    require(prediction['schema'] == 'expanded-predictions/1' and prediction['role'] == partition.role,
            'Prediction role mismatch')
    require(prediction['bindings'] == partition.bindings, 'Prediction provenance mismatch')
    expected = [f'{r["conversation_id"]}:{r["utterance_id"]}' for r in partition.rows]
    require(prediction['row_keys'] == expected, 'Prediction rows reordered/missing')
    require(len(prediction['logits']) == len(expected), 'Prediction length differs')
    probabilities(prediction['logits'])


def seed_summary(metrics):
    require(set(metrics) == set(SEEDS), 'All three registered seeds required')
    flat = {}
    def flatten(value, prefix=''):
        if isinstance(value, dict):
            for key, item in value.items():
                yield from flatten(item, prefix + '/' + str(key))
        elif value is None or type(value) in (int, float):
            yield prefix, value
    items = {seed: dict(flatten(value)) for seed, value in metrics.items()}
    for key in set.union(*(set(item) for item in items.values())):
        values = [item[key] for item in items.values() if item.get(key) is not None]
        flat[key] = dict(mean=float(np.mean(values)) if values else None,
                         std_sample=float(np.std(values, ddof=1)) if len(values) > 1 else None,
                         defined_seeds=len(values))
    return flat


def paired_bootstrap(left, right, partition, left_thresholds=(.5,)*9, right_thresholds=(.5,)*9,
                     *, repetitions=2000, seed=20261107, unit='scenario_family_id'):
    require(unit in ('scenario_family_id', 'conversation_id') and repetitions > 0, 'Invalid bootstrap unit/budget')
    require(set(left) == set(right) == set(SEEDS), 'Paired seeds must match')
    for prediction in list(left.values()) + list(right.values()):
        validate_predictions(prediction, partition)
    y = targets(partition.rows)[:, 0]
    lp = {s: probabilities(p['logits'])[:, 0] for s, p in left.items()}
    rp = {s: probabilities(p['logits'])[:, 0] for s, p in right.items()}
    lt, rt = threshold_vector(left_thresholds)[0], threshold_vector(right_thresholds)[0]
    groups = sorted({r[unit] for r in partition.rows})
    indices = {g: [i for i, r in enumerate(partition.rows) if r[unit] == g] for g in groups}
    rng, differences = np.random.default_rng(seed), []
    for _ in range(repetitions):
        ids = [i for g in rng.choice(groups, len(groups), replace=True) for i in indices[g]]
        if not y[ids].any() or y[ids].all():
            continue
        differences.append(float(np.mean([binary_metrics(y[ids], rp[s][ids], rt)['f1'] -
                                          binary_metrics(y[ids], lp[s][ids], lt)['f1'] for s in SEEDS])))
    return dict(unit=unit, repetitions=repetitions, valid_repetitions=len(differences),
                invalid_reason='resample_missing_positive_or_negative', seed=seed,
                delta_f1_mean=float(np.mean(differences)) if differences else None,
                ci95=np.percentile(differences, [2.5, 97.5]).tolist() if differences else None)


def validate_final_plan(plan):
    """A separately frozen model registry permits A0/A_epoch as well as selected B/C."""
    from expanded_common import PROTOCOL_SHA, ARMS
    from expanded_selection import validate_frozen
    require(plan.get('schema') == 'expanded-final-plan/1' and plan.get('protocol_sha256') == PROTOCOL_SHA,
            'Unknown final-evaluation plan')
    require(plan.get('selection_source') == 'validation' and plan['label_order'] == list(LABELS), 'Final selection must be validation-only')
    validate_frozen(plan['frozen_b'])
    require(bool(plan['models']), 'Final model registry is empty')
    for arm, entries in plan['models'].items():
        require(arm in ARMS and arm != 'B_threshold', 'Invalid final model arm')
        require(set(entries) == {str(s) for s in SEEDS}, 'Final plan must register all seeds for each arm')
        require(len({entry['epoch'] for entry in entries.values()}) == 1, 'All seeds must use the same selected epoch')
        for entry in entries.values():
            threshold_vector(entry['thresholds'])
            require(set(entry['checkpoint']) == {'path', 'sha256'} and entry['threshold_version'], 'Missing immutable checkpoint/threshold version')
            if arm == 'A0':
                require(entry['epoch'] == 1 and entry['thresholds'] == [.5]*9, 'A0 must remain the 1-epoch/.5 baseline')
            elif arm in ('A_epoch', 'B_sqrt5_legacy'):
                require(entry['epoch'] in (1, 2, 3) and entry['thresholds'] == [.5]*9, 'Unregistered epoch/threshold policy')
            elif arm in ('B_ratio', 'C_approved'):
                require(entry['epoch'] == plan['frozen_b']['epoch'], 'B/C must reuse the selected B epoch')
                require(entry['thresholds'] in ([.5]*9, plan['frozen_b']['thresholds']), 'Unregistered B/C thresholds')
                if arm == 'C_approved':
                    require(entry['thresholds'] == plan['frozen_b']['thresholds'] and
                            entry['threshold_version'] == plan['frozen_b']['version'], 'C must preserve B thresholds')
            elif arm == 'B_step_matched':
                require(entry['thresholds'] == plan['frozen_b']['thresholds'] and
                        entry['threshold_version'] == plan['frozen_b']['version'], 'Step control must preserve B thresholds')
    return plan
