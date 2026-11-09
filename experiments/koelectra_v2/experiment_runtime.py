"""Offline configuration, path and DataLoader checks; no training entry point."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
import platform
import re
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
REF=ROOT/'artifacts/v1_reference/pr35_9bab7e383928'
REPORTS=ROOT/'reports/v2_experiment_design'
sys.path.insert(0,str(REF))
sys.path.insert(0,str(ROOT/'dataset/scripts'))


class ExperimentError(ValueError):pass
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return json.loads(path.read_text(encoding='utf-8'))
def rows(path):return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]


def output_path(config,seed,run_id):
    if type(seed) is not int or seed not in config['training']['seeds']:raise ExperimentError('Unregistered seed')
    exp=config['experiment_id']
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',exp) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',run_id):raise ExperimentError('Unsafe experiment/run slug')
    base=(ROOT/config['output']['root']).resolve()
    expected=(ROOT/'artifacts/v2_comparison_runs').resolve()
    if base!=expected or config['output']['overwrite'] is not False or config['output']['checkpoint_name']!='model.pt':raise ExperimentError('Only isolated no-overwrite comparison output allowed')
    target=(base/exp/f'seed_{seed}'/run_id).resolve()
    if not target.is_relative_to(expected):raise ExperimentError('Output escapes allowed root')
    if target.exists():raise ExperimentError('Existing run directory must never be reused')
    return target


def reserve_output(config,seed,run_id):
    target=output_path(config,seed,run_id)
    target.mkdir(parents=True,exist_ok=False)
    return target


def validate_manifest(plan,ids):
    if set(plan['conversation_to_split'])!=ids or any(s not in ('train','validation','test') for s in plan['conversation_to_split'].values()):raise ExperimentError('Split coverage invalid')
    members=[c for group in plan['groups'].values() for c in group]
    if len(members)!=len(set(members)) or set(members)!=ids:raise ExperimentError('Group membership missing or duplicated')
    for group in plan['groups'].values():
        if len({plan['conversation_to_split'][c] for c in group})!=1:raise ExperimentError('Group leakage')


def validate_config(config):
    from risk_speech_ai.labels import LABELS
    if type(config['config_schema_version']) is not int or config['config_schema_version']!=1 or config['arm'] not in ('A','B','C'):raise ExperimentError('Unsupported config')
    if config['execution']!={'allowed_mode':'preflight','training_enabled':False,'test_prediction_enabled':False}:raise ExperimentError('This tool is preflight only')
    if config['input']['label_order']!=list(LABELS) or config['input']['max_history_utterances']!=5 or config['input']['max_sequence_length']!=512:raise ExperimentError('Input contract changed')
    if config['evaluation']['risk_threshold']!=.5 or config['evaluation']['type_thresholds']!=[.5]*8:raise ExperimentError('Primary thresholds must remain fixed')
    if config['model']['original_v1_checkpoint_required'] or config['model']['original_v1_checkpoint_restored']:raise ExperimentError('Missing historic weights must not be represented as restored')
    if config['model']['name']!='monologg/koelectra-base-v3-discriminator' or config['model']['revision']!='68b30cd259f34a4b5aa8786392612ba2a2617fcc' or config['model']['tokenizer_revision']!=config['model']['revision']:raise ExperimentError('Pinned public model/tokenizer changed')
    if config['training']['epochs']!=1 or config['training']['batch_size']!=8 or config['training']['learning_rate']!=2e-5:raise ExperimentError('Unregistered optimization setting')
    if config['data']['synthetic_train'] and (config['arm']!='C' or config['data']['synthetic_train']['include_unapproved']):raise ExperimentError('Unapproved synthetic mixing')
    if (config['arm']=='C')!=(config['data']['synthetic_train'] is not None):raise ExperimentError('Only C requires a synthetic source')
    if config['data']['synthetic_train']:
        synthetic=config['data']['synthetic_train']
        if sha(ROOT/synthetic['path'])!=synthetic['sha256']:raise ExperimentError('Synthetic source hash mismatch')
    if (config['arm']=='A')!=(config['loss']['type_pos_weight'] is None):raise ExperimentError('Unregistered loss ablation')
    for path_key,hash_key in (('labels_path','labels_sha256'),('text_path','text_sha256'),('split_manifest','split_sha256')):
        p=ROOT/config['data'][path_key]
        if not p.is_file() or sha(p)!=config['data'][hash_key]:raise ExperimentError(f'Input hash mismatch: {path_key}')
    plan=read(ROOT/config['data']['split_manifest'])
    labels=rows(ROOT/config['data']['labels_path'])
    ids={r['conversation_id'] for r in labels}
    validate_manifest(plan,ids)
    if config['loss']['type_pos_weight']:
        spec=config['loss']['type_pos_weight']; p=ROOT/spec['manifest']
        if sha(p)!=spec['sha256']:raise ExperimentError('Loss weight manifest mismatch')
        weights=read(p)
        if weights['split_candidate_sha256']!=config['data']['split_sha256'] or weights['computed_from']!='original v1 TRAIN partition only; C reuses B values without recomputation':raise ExperimentError('Weights must use shared original TRAIN only')
        values=weights['values']
        if len(values)!=8 or any(type(v) not in (int,float) or not math.isfinite(v) or not 0<v<=5 for v in values):raise ExperimentError('Invalid positive weights')
    return plan


def samples_for(config,role):
    if role not in ('train','validation','test'):raise ExperimentError('Explicit partition required')
    plan=validate_config(config)
    if config['arm']=='C':
        raise ExperimentError('C BLOCKED: final-approved synthetic=0; do not silently omit or promote candidates')
    ids={c for c,s in plan['conversation_to_split'].items() if s==role}
    labels=[r for r in rows(ROOT/config['data']['labels_path']) if r['conversation_id'] in ids]
    texts=[r for r in rows(ROOT/config['data']['text_path']) if r['conversation_id'] in ids]
    from risk_speech_ai.train_cli import build_safe_training_samples
    built,_=build_safe_training_samples(labels,texts)
    if len(built.samples)!=len(labels):raise ExperimentError('Unexpected sample exclusion')
    return built.samples


def loss_values(output,risk_target,type_targets,config):
    """Loss implementation for the planned B/C change; never backward here."""
    import torch
    from torch import nn
    pw=config['loss']['type_pos_weight']
    weight=None if pw is None else torch.tensor(read(ROOT/pw['manifest'])['values'],dtype=output.type_logits.dtype,device=output.type_logits.device)
    risk=nn.BCEWithLogitsLoss()(output.risk_logits,risk_target)
    types=nn.BCEWithLogitsLoss(pos_weight=weight)(output.type_logits,type_targets)
    return risk+types,risk,types


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,default=HERE/'configs/A.json')
    parser.add_argument('--run-id',default='preflight-20261106')
    parser.add_argument('--load-public-base',action='store_true')
    args=parser.parse_args()
    cache=ROOT/'artifacts/v2_experiment_assets/hf'
    os.environ.update(HF_HOME=str(cache),HF_HUB_CACHE=str(cache/'hub'),HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1')
    import torch
    import transformers
    from risk_speech_ai.dataset import RiskSpeechDataset,make_training_dataloader
    from risk_speech_ai.tokenization import load_koelectra_tokenizer,build_model_input
    from risk_speech_ai.training import TrainingConfig,create_training_model
    cfg=read(args.config);plan=validate_config(cfg)
    torch.set_num_threads(2)
    results=dict(experiment_id=cfg['experiment_id'],training_executed=False,optimizer_created=False,checkpoint_written=False,
        actual_model_performance_computed=False,eval_gold_verified=False,test_predictions_generated=False,
        split_plan_status=plan['status'],environment=dict(python=sys.version,platform=platform.platform(),torch=torch.__version__,transformers=transformers.__version__),partitions={})
    results['output_paths']={str(seed):str(output_path(cfg,seed,args.run_id)) for seed in cfg['training']['seeds']}
    if cfg['arm']=='C':
        try:samples_for(cfg,'train')
        except ExperimentError as e:results.update(status='BLOCKED_EXPECTED_NO_APPROVED_SYNTHETIC',reason=str(e))
        else:raise ExperimentError('C improperly opened')
    else:
        tokenizer=load_koelectra_tokenizer(cfg['model']['tokenizer_revision'])
        first_batch=None
        all_text={(r['conversation_id'],r['utterance_id']):r['tuned_text'] for r in rows(ROOT/cfg['data']['text_path'])}
        for role in ('train','validation','test'):
            samples=samples_for(cfg,role);prepared=[build_model_input(s.history_texts,s.current_text,tokenizer=tokenizer) for s in samples]
            ds=RiskSpeechDataset(samples,tokenizer=tokenizer)
            loader=make_training_dataloader(ds,tokenizer=tokenizer,batch_size=8,shuffle=False)
            count=0;batches=0;first=None
            for batch in loader:
                n,width=batch['input_ids'].shape;batches+=1
                assert all(v.device.type=='cpu' for v in batch.values()) and width<=512
                assert all(batch[k].dtype==torch.int64 and batch[k].shape==batch['input_ids'].shape for k in ('input_ids','attention_mask','token_type_ids'))
                assert batch['risk_target'].shape==(n,1) and batch['type_targets'].shape==(n,8)
                assert batch['risk_target'].dtype==batch['type_targets'].dtype==torch.float32
                ss=samples[count:count+n]
                assert torch.equal(batch['risk_target'],torch.tensor([[s.risk_target] for s in ss],dtype=torch.float32))
                assert torch.equal(batch['type_targets'],torch.tensor([s.type_targets for s in ss],dtype=torch.float32))
                for i,s in enumerate(ss):
                    expected=[(u,t) for (c,u),t in all_text.items() if c==s.conversation_id and u<s.utterance_id]
                    assert s.history_texts==[t for u,t in sorted(expected)[-5:]] and s.current_text==all_text[s.conversation_id,s.utterance_id]
                    p=prepared[count+i];length=p.token_count
                    for key in ('input_ids','attention_mask','token_type_ids'):assert batch[key][i,:length].tolist()==getattr(p,key)
                    assert not batch['attention_mask'][i,length:].any()
                    assert all(x==tokenizer.pad_token_id for x in batch['input_ids'][i,length:].tolist())
                if first is None:first={k:dict(shape=list(v.shape),dtype=str(v.dtype),device=str(v.device)) for k,v in batch.items()}
                if first_batch is None:first_batch=batch
                count+=n
            assert count==len(samples) and batches==math.ceil(count/8)
            results['partitions'][role]=dict(status='PASS_TECHNICAL_PREFLIGHT_NOT_GOLD_EVALUATION',samples=count,batches=batches,
                first_batch=first,max_history=max(len(s.history_texts) for s in samples),min_tokens=min(p.token_count for p in prepared),
                max_tokens=max(p.token_count for p in prepared),dropped_history=sum(p.dropped_history_count for p in prepared))
        if args.load_public_base:
            model=create_training_model(TrainingConfig(data_version='v1_retrained_baseline-preflight',epochs=1,seed=42,
                model_revision=cfg['model']['revision'],tokenizer_revision=cfg['model']['tokenizer_revision'])).eval()
            # No forward/optimizer: prove genuine encoder initialization and heads.
            results['public_base_loading']=dict(status='PASS_PINNED_PRETRAINED_ENCODER_NEW_RANDOM_HEADS',
                parameter_count=sum(p.numel() for p in model.parameters()),hidden_size=model.encoder.config.hidden_size,
                risk_shape=list(model.risk_classifier.weight.shape),type_shape=list(model.type_classifier.weight.shape),
                no_gradients=all(p.grad is None for p in model.parameters()),original_v1_checkpoint_restored=False)
            del model
        results['status']='PASS_PREFLIGHT_TRAINING_BLOCKED_PENDING_REVIEW'
    REPORTS.mkdir(parents=True,exist_ok=True)
    (REPORTS/f"preflight_{cfg['arm']}.json").write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(results,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
