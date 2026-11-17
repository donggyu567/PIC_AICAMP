"""Fixed-threshold metrics, type loss, safe stopping and family uncertainty."""
from __future__ import annotations

import math
from .common import FOCUS, LABELS, bootstrap, require
from .data import allowed_role

GATES = dict(binary_recall_drop_max=.02, binary_f1_drop_max=.01, other_macro_f1_drop_max=.02,
             other_type_recall_drop_max=.10, focus_f1_gain_min=.05, focus_ap_drop_max=.02,
             normal_false_alert_increase_max=0)


def type_losses(output, risk, types):
    import torch
    from torch.nn import functional as F
    unweighted = F.binary_cross_entropy_with_logits(output.type_logits, types, reduction='none')
    weighted = F.binary_cross_entropy_with_logits(output.type_logits, types,
                pos_weight=torch.full((8,), 10., device=types.device), reduction='none')
    risk_loss = F.binary_cross_entropy_with_logits(output.risk_logits, risk)
    return dict(risk=float(risk_loss.detach()),
                types_unweighted=unweighted.detach().mean(0).tolist(),
                types_weighted=weighted.detach().mean(0).tolist())


def normal_groups(rows, probabilities):
    groups = {}
    for category in sorted({r['category'] for r in rows if r['hard_negative']}):
        ids = [i for i, r in enumerate(rows) if r['hard_negative'] and r['category'] == category]
        groups[category] = dict(n=len(ids), risk_fp=int(sum(probabilities[i][0] >= .5 for i in ids)),
            type_fp={l:int(sum(probabilities[i][j+1] >= .5 for i in ids)) for j,l in enumerate(LABELS)})
    return groups


def score_logits(partition, logits):
    allowed_role(partition.role)
    bootstrap()
    from expanded_evaluation import evaluate_logits, probabilities
    rows = partition.rows()
    values = probabilities(logits)
    require(len(rows) == len(values), 'Prediction row alignment differs')
    metrics = evaluate_logits(rows, logits, [.5]*9)
    metrics['normal_categories'] = normal_groups(rows, values)
    metrics['evaluation_scope'] = 'validation_selection_not_final_test' if partition.role == 'validation' else 'train_in_sample'
    metrics['label_order'] = list(LABELS)
    metrics['probability_distributions'] = {
        label:{name:dict(n=len(ps), mean=float(ps.mean()), min=float(ps.min()), max=float(ps.max())) if len(ps) else None
               for name, ps in [('positive', values[[bool(r['is_phishing']) if j==0 else label in r['labels'] for r in rows],j]),
                                ('negative', values[[not (bool(r['is_phishing']) if j==0 else label in r['labels']) for r in rows],j])]}
        for j,label in enumerate(('risk',)+LABELS)}
    return metrics


def evaluate_split(model, tokenizer, partition):
    allowed_role(partition.role)
    bootstrap()
    from risk_speech_ai.dataset import RiskSpeechDataset, make_training_dataloader
    import torch
    samples = partition.samples()
    loader = make_training_dataloader(RiskSpeechDataset(samples, tokenizer=tokenizer), tokenizer=tokenizer,
                                      batch_size=8, shuffle=False)
    was_training = model.training
    logits = []
    try:
        model.eval()
        with torch.inference_mode():
            for batch in loader:
                output = model(**{k:batch[k] for k in ('input_ids','attention_mask','token_type_ids')})
                logits.extend(torch.cat([output.risk_logits,output.type_logits],dim=1).tolist())
    finally:
        model.train(was_training)
    metrics = score_logits(partition, logits)
    return dict(role=partition.role, data_sha256=partition.data_sha256,
                row_keys=[f'{s.conversation_id}:{s.utterance_id}' for s in samples],
                logits=logits, metrics=metrics)


def _defined(value):
    return type(value) in (int, float) and math.isfinite(value)


def safety(baseline, candidate):
    reasons = []
    for key, limit in [('recall',.02),('f1',.01)]:
        b, c = baseline['binary'][key], candidate['binary'][key]
        if not (_defined(b) and _defined(c)) or c < b-limit-1e-12:
            reasons.append('binary_'+key+'_regression_or_undefined')
    other = [l for l in LABELS if l not in FOCUS]
    bs, cs = [], []
    for l in other:
        b, c = baseline['per_type'][l], candidate['per_type'][l]
        if not all(_defined(v) for v in [b['recall'], c['recall'], b['f1'], c['f1']]):
            reasons.append(l+'_undefined')
            continue
        bs.append(b['f1']); cs.append(c['f1'])
        if c['recall'] < b['recall']-.10-1e-12:
            reasons.append(l+'_recall_regression')
    if len(bs)!=6 or sum(cs)/6 < sum(bs)/6-.02-1e-12:
        reasons.append('other_macro_f1_regression_or_undefined')
    bc, cc = baseline['conversations'], candidate['conversations']
    if bc['normal'] <= 0 or cc['normal'] != bc['normal'] or cc['normal_false_alerts'] > bc['normal_false_alerts']:
        reasons.append('normal_conversation_regression_or_support_changed')
    return reasons


def apply_gates(baseline, candidate, old_baseline, old_candidate, *, epoch):
    require(epoch in (1,2), 'Maximum two epochs')
    reasons = safety(baseline, candidate) + ['old_validation:'+r for r in safety(old_baseline,old_candidate)]
    bfp = baseline['conversations']['normal_false_alerts']
    cfp = candidate['conversations']['normal_false_alerts']
    target = cfp <= (bfp-1 if bfp else 0)
    focus_defined = True
    for l in FOCUS:
        b,c = baseline['per_type'][l],candidate['per_type'][l]
        if not all(_defined(v) for v in [b['f1'], c['f1'], b['average_precision'], c['average_precision']]):
            focus_defined = target = False
        else:
            target = target and c['f1'] >= b['f1']+.05-1e-12 and c['average_precision'] >= b['average_precision']-.02-1e-12
    safe = not reasons
    allow = epoch == 1 and safe and not target and focus_defined and all(
        candidate['per_type'][l]['average_precision'] >= baseline['per_type'][l]['average_precision'] for l in FOCUS) and any(
        candidate['per_type'][l]['f1'] > baseline['per_type'][l]['f1'] for l in FOCUS)
    return dict(epoch=epoch, safe=safe, safety_failures=reasons, targets_passed=bool(target),
                adopt=bool(safe and target), allow_epoch2=bool(allow),
                normal_fp_outcome='zero_maintained_not_improved' if not bfp and not cfp else 'compare_counts',
                final_generalization_claim=False)


def family_paired_uncertainty(partition, baseline, candidate, *, repetitions=1000):
    allowed_role(partition.role)
    require(baseline['row_keys'] == candidate['row_keys'] and baseline['data_sha256'] == candidate['data_sha256'] == partition.data_sha256,
            'Unpaired predictions')
    import numpy as np
    bootstrap()
    from expanded_evaluation import probabilities
    rows = partition.rows()
    require(baseline['row_keys']==[f"{r['conversation_id']}:{r['utterance_id']}" for r in rows], 'Prediction keys do not match partition order')
    bp, cp = probabilities(baseline['logits']), probabilities(candidate['logits'])
    family = sorted({r['scenario_family_id'] for r in rows})
    indices = {f:[i for i,r in enumerate(rows) if r['scenario_family_id']==f] for f in family}
    rng=np.random.default_rng(42)
    deltas={l:[] for l in ('risk',)+FOCUS}
    for _ in range(repetitions):
        ids=[i for f in rng.choice(family,len(family),replace=True) for i in indices[f]]
        for l in deltas:
            j=0 if l=='risk' else LABELS.index(l)+1
            y=np.asarray([rows[i]['is_phishing'] if j==0 else l in rows[i]['labels'] for i in ids],dtype=bool)
            if not y.any() or y.all():
                continue
            def f1(p):
                pred=p[ids,j]>=.5; tp=int((pred & y).sum()); fp=int((pred & ~y).sum()); fn=int((~pred & y).sum())
                return 2*tp/(2*tp+fp+fn)
            deltas[l].append(f1(cp)-f1(bp))
    return dict(unit='scenario_family_id',families=len(family),repetitions=repetitions,seed=42,
                delta_f1={l:dict(valid=len(v),ci95=np.percentile(v,[2.5,97.5]).tolist() if v else None) for l,v in deltas.items()},
                limitation='Small selection set; intervals do not establish final TEST improvement')
