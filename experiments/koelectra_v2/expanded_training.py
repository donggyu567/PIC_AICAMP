"""Fresh-public-model A/B/C training; real runs require validated external evidence."""
from __future__ import annotations

from dataclasses import asdict
import math
import warnings
import numpy as np
import torch

from expanded_common import (LABELS, REVISION, PROTOCOL_SHA, compile_runtime, validate_runtime,
                             digest, require, sha, write_json)
from expanded_data import check_disjoint
from expanded_evaluation import infer_partition, evaluate_logits
from expanded_checkpoint import RunStore
from risk_speech_ai.training import TrainingConfig, _metadata
from risk_speech_ai.dataset import RiskSpeechDataset, make_training_dataloader


def positive_weights(partition, *, policy='ratio10', label_order=LABELS):
    partition.verify({'train'})
    require(list(label_order) == list(LABELS), 'Weight label order mismatch')
    require(policy in ('ratio10', 'sqrt5'), 'Unknown loss-weight recipe')
    values, unsupported = [], []
    for label in LABELS:
        positive = sum(label in row['labels'] for row in partition.rows)
        if positive == 0:
            values.append(1.)
            unsupported.append(label)
            warnings.warn(f'{label}: zero TRAIN positives; weight=1, unsupported detection', RuntimeWarning)
        else:
            ratio = (len(partition.rows) - positive) / positive
            values.append(min(10., max(1., ratio)) if policy == 'ratio10' else min(5., math.sqrt(ratio)))
    require(all(math.isfinite(v) and v >= 0 for v in values), 'Non-finite/negative positive weight')
    return dict(values=values, label_order=list(LABELS), unsupported=unsupported,
                source='original_TRAIN_only', train_bindings=partition.bindings, policy=policy)


def losses(output, risk, types, weights):
    from risk_speech_ai.training import compute_losses
    base = compute_losses(output, risk, types)
    require(len(weights) == 8 and all(math.isfinite(w) and w >= 0 for w in weights), 'Invalid loss weights')
    tensors = [output.risk_logits, output.type_logits, risk, types]
    require(all(torch.isfinite(t).all().item() for t in tensors), 'Non-finite logits/targets')
    require(all(torch.isin(t, torch.tensor([0., 1.], device=t.device)).all().item() for t in (risk, types)), 'Targets must be binary')
    weighted = torch.nn.functional.binary_cross_entropy_with_logits(output.type_logits, types,
                 pos_weight=torch.tensor(weights, dtype=output.type_logits.dtype, device=output.type_logits.device))
    total = base.risk_loss + weighted
    require(torch.isfinite(total).item(), 'Non-finite BCE loss')
    return total, base.risk_loss, weighted


def step_budget(base, synthetic, epochs, *, batch_size=8):
    base.verify({'train'})
    synthetic.verify({'synthetic_train'})
    require(len(synthetic.rows) > 0, 'C size/approval not confirmed')
    check_disjoint(base, synthetic)
    return math.ceil((len(base.rows) + len(synthetic.rows)) / batch_size) * epochs


def train(config, base, validation, tokenizer, *, run_id, synthetic=None,
          receipt=None, store_root=None, fixture_model_factory=None, cache=None):
    validate_runtime(config)
    base.verify({'train'})
    validation.verify({'validation'})
    require(any(row['is_phishing'] for row in validation.rows), 'VALIDATION needs risk positives for epoch selection')
    check_disjoint(base, validation)
    require(base.fixture == validation.fixture, 'Fixture/production data mixed')
    fixture = base.fixture
    from expanded_data import SealedReceipt
    require(isinstance(receipt, SealedReceipt), 'External TEST sealing receipt required before training')
    receipt = receipt.verify()
    require(receipt['split_sha256'] == base.bindings['split_sha256'], 'TEST sealing split differs')
    require(sha(base.manifest_path) == base.manifest_sha256, 'TRAIN manifest changed')
    arm, seed = config['arm'], config['seed']
    rows = base.samples()
    if arm in ('C_approved', 'B_step_matched'):
        weights = list(config['frozen_weights'])
    else:
        weights = [1.] * 8 if config['weight_policy'] == 'none' else positive_weights(base, policy=config['weight_policy'])['values']
    max_steps, epochs = None, config['epochs']
    bindings = dict(train=base.bindings, validation=validation.bindings,
                    test_receipt_sha256=digest(receipt))
    if arm in ('C_approved', 'B_step_matched'):
        require(synthetic is not None, 'C blocked: no approved synthetic TRAIN manifest')
        synthetic.verify({'synthetic_train'})
        require(synthetic.fixture == fixture, 'Fixture/production data mixed')
        check_disjoint(base, validation, synthetic)
        frozen = config['frozen_selection']
        from expanded_selection import validate_frozen_checkpoints
        validate_frozen_checkpoints(frozen, fixture=fixture)
        require(frozen['train_bindings'] == base.bindings and frozen['validation_bindings'] == validation.bindings,
                'B selection belongs to different train/validation evidence')
        weights = list(config['frozen_weights'])
        bindings['synthetic_train'] = synthetic.bindings
        if arm == 'C_approved':
            rows += synthetic.samples()
        else:
            max_steps = step_budget(base, synthetic, epochs)
            epochs = math.ceil(max_steps / math.ceil(len(rows) / 8))
    require(fixture or fixture_model_factory is None, 'Model injection is limited to controlled temporary fixtures')
    cfg = TrainingConfig(data_version='koelectra-expansion-20261109-v1', epochs=epochs, seed=seed,
                         batch_size=8, learning_rate=2e-5, weight_decay=.01,
                         model_revision=REVISION, tokenizer_revision=REVISION)
    # The production path always initializes from the same pinned public encoder, never v1/B weights.
    from risk_speech_ai.training import set_training_seed
    set_training_seed(seed)
    from expanded_assets import fresh_public_model
    model = fixture_model_factory(seed) if fixture_model_factory else fresh_public_model(seed, **({'cache': cache} if cache is not None else {}))
    model.cpu()
    initial_heads = digest({name: tensor.detach().tolist() for name, tensor in model.state_dict().items()
                            if name.startswith(('risk_classifier.', 'type_classifier.'))})
    # Tokenizer/config validation happens before any optimizer update or output reservation.
    metadata = _metadata(model, tokenizer, cfg, torch.device('cpu'))
    require(metadata['model_revision'] == metadata['tokenizer_revision'] == REVISION, 'Initialization revision differs')
    loader = make_training_dataloader(RiskSpeechDataset(rows, tokenizer=tokenizer), tokenizer=tokenizer,
                                      batch_size=8, seed=seed, shuffle=True)
    store = RunStore(arm, seed, run_id, fixture=fixture, **({'root': store_root} if store_root is not None else {}))
    optimizer = torch.optim.AdamW(model.parameters(), lr=2e-5, weight_decay=.01)
    history, references, steps = [], [], 0
    for epoch in range(1, epochs+1):
        model.train()
        total_sum, seen = 0., 0
        for batch in loader:
            optimizer.zero_grad(set_to_none=True)
            output = model(**{k: batch[k] for k in ('input_ids', 'attention_mask', 'token_type_ids')})
            total, risk_loss, type_loss = losses(output, batch['risk_target'], batch['type_targets'], weights)
            total.backward()
            require(all(p.grad is None or torch.isfinite(p.grad).all().item() for p in model.parameters()), 'Non-finite gradient')
            optimizer.step()
            require(all(torch.isfinite(p).all().item() for p in model.parameters()), 'Non-finite updated parameter')
            steps += 1
            count = len(batch['input_ids'])
            seen += count
            total_sum += total.item() * count
            if max_steps is not None and steps >= max_steps:
                break
        prediction = infer_partition(model, tokenizer, validation, seed=seed, epoch=epoch, arm=arm)
        metrics = evaluate_logits(validation.rows, prediction['logits'], [.5]*9)
        record = dict(epoch=epoch, optimizer_steps=steps, train_loss=total_sum/seen,
                      validation_binary_f1=metrics['binary']['f1'])
        history.append(record)
        ext = dict(schema='expanded-checkpoint-extension/1', fixture=fixture, protocol_sha256=PROTOCOL_SHA,
                   runtime=config, runtime_sha256=digest(config), label_order=list(LABELS), arm=arm, seed=seed,
                   epoch=epoch, optimizer_steps=steps, bindings=bindings, weights=weights,
                   threshold_version=config['threshold_version'], thresholds=config['thresholds'],
                   initialization='fresh_public_encoder' if not fixture else 'temporary_tiny_Electra_fixture',
                   initial_heads_sha256=initial_heads, max_steps=max_steps)
        payload = dict(checkpoint_schema_version='v1', model_state_dict=model.state_dict(),
                       optimizer_state_dict=optimizer.state_dict(), epoch=epoch, training_config=asdict(cfg),
                       label_order=list(LABELS), base_model=metadata['base_model'], metadata=metadata,
                       epoch_losses=history, sample_count=len(rows), step_count=steps, expanded_metadata=ext)
        reference = store.epoch(payload)
        references.append(reference)
        prediction['checkpoint'] = reference
        write_json(store.path / f'validation_epoch_{epoch:03d}.json', prediction)
        write_json(store.path / f'epoch_{epoch:03d}_metrics.json', dict(training=record, validation=metrics))
        if max_steps is not None and steps >= max_steps:
            break
    scores = [(r['validation_binary_f1'], i) for i, r in enumerate(history) if r['validation_binary_f1'] is not None]
    require(bool(scores), 'No defined validation F1 for best checkpoint')
    best = min(scores, key=lambda item: (-round(item[0], 12), item[1]))[1]
    store.alias('best', references[best])
    store.alias('last', references[-1])
    result = dict(arm=arm, seed=seed, history=history, best_epoch=history[best]['epoch'],
                  last_epoch=history[-1]['epoch'], optimizer_steps=steps, max_steps=max_steps,
                  references=references, initial_heads_sha256=initial_heads, weights=weights,
                  best_scope='per_seed_provisional; final epoch selection averages seeds42/43/44')
    write_json(store.path / 'run.json', result)
    return result
