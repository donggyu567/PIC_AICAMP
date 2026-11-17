"""One fixed warm-start trajectory, gated before parent allocation or updates."""
from __future__ import annotations

import argparse
from copy import deepcopy
import ctypes
import math
import re
import shutil
import time
import hashlib
import json
from datetime import datetime,timezone

from .common import (V3, RUNS, LABELS, PARENT_SHA, REVISION, bootstrap, create_json,
                     digest, inside, read_json, require, sha)
from .data import load_training_inputs
from .checkpoint import load_v2_start, load_v3_state, runtime, save_v3_checkpoint, verify_parent
from .diagnostics import GATES, apply_gates, evaluate_split, family_paired_uncertainty, type_losses


def code_inventory():
    return {p.relative_to(V3).as_posix():sha(p) for folder in ['src','tests','configs']
            for p in sorted((V3/folder).rglob('*')) if p.is_file() and p.suffix in ('.py','.json')}


def load_config():
    c=read_json(V3/'configs/lite_seed42.json')
    fixed=dict(seed=42,batch_size=8,learning_rate=5e-6,weight_decay=.01,type_pos_weight=[10]*8,
               thresholds=[.5]*9,epochs_default=1,epochs_max=2,optimizer_steps_per_epoch=106,
               max_optimizer_steps=212,cpu_threads=2,gradient_checkpointing=True,optimizer_reset=True,
               precision='float32',parent_sha256=PARENT_SHA,revision=REVISION,label_order=list(LABELS),gates=GATES,
               schema='koelectra-v3-lite-config/1',purpose='internal_experiment')
    require(c==fixed, 'Fixed phase-one config changed; no search/overrides allowed')
    return c


def resources():
    import os
    from ctypes import wintypes
    require(os.name=='nt', 'Resource preflight implemented for the specified Windows host')
    class Memory(ctypes.Structure):
        _fields_=[('length',wintypes.DWORD),('load',wintypes.DWORD)]+[(k,ctypes.c_ulonglong) for k in
            ('physical_total','physical_available','commit_limit','commit_available','virtual_total','virtual_available','extended')]
    mem=Memory(); mem.length=ctypes.sizeof(mem)
    require(ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(mem)), 'Cannot inspect Windows memory')
    result={k:int(getattr(mem,k)) for k,_ in mem._fields_ if k not in ('length','extended')}
    result.update(cpu_count=os.cpu_count(),disk_free=shutil.disk_usage(V3).free)
    result['training_capacity_ok']=(result['commit_available']>=4*1024**3 and result['physical_available']>=512*1024**2 and
                                    result['disk_free']>=6*1024**3 and bool(result['cpu_count']))
    return result


def preflight(manifest_path, regression_receipt, *, data_mode='reviewed'):
    config=load_config()
    # Data/review failure precedes model allocation or any run/checkpoint write.
    require(data_mode in ('reviewed','research_synthetic_v3'),'Unknown data route')
    if data_mode=='research_synthetic_v3':
        from .research_data import load_research_inputs
        train,validation,old_val,bindings=load_research_inputs(manifest_path)
    else:
        train,validation,old_val,bindings=load_training_inputs(manifest_path)
    receipt_path=inside(regression_receipt,V3/'reports')
    receipt=read_json(receipt_path)
    require(receipt.get('schema')=='v3-lite-regression/1' and receipt.get('status')=='PASS' and
            receipt.get('tests_run',0)>0 and receipt.get('failures')==0 and receipt.get('errors')==0 and
            receipt.get('skipped')==0 and receipt.get('code_sha256')==digest(code_inventory()), 'Fresh passing regression receipt required')
    verify_parent()
    res=resources()
    require(res['training_capacity_ok'], 'Insufficient CPU/memory/commit/disk headroom')
    return config,train,validation,old_val,bindings,res


def new_optimizer(model):
    import torch
    optimizer=torch.optim.AdamW(model.parameters(),lr=5e-6,weight_decay=.01,foreach=False)
    require(not optimizer.state, 'Warm start must use a new empty optimizer')
    return optimizer


def train_one_epoch(model,loader,optimizer,*,epoch,step_offset=0,step_limit=212,progress=None):
    """Low-level batch primitive. Unit tests use only tiny temporary Electra weights."""
    bootstrap()
    from expanded_training import losses
    import torch
    require(epoch in (1,2) and step_offset+len(loader)<=step_limit, 'Epoch/update budget exceeded')
    model.train()
    start=time.monotonic(); seen=0; steps=0; total_sum=risk_sum=type_sum=0.
    unweighted=[0.]*8; weighted=[0.]*8
    for batch in loader:
        optimizer.zero_grad(set_to_none=True)
        output=model(**{k:batch[k] for k in ('input_ids','attention_mask','token_type_ids')})
        total,risk,types=losses(output,batch['risk_target'],batch['type_targets'],[10.]*8)
        require(torch.isfinite(total).item(), 'Nonfinite loss')
        diagnostic=type_losses(output,batch['risk_target'],batch['type_targets'])
        total.backward()
        require(all(p.grad is None or torch.isfinite(p.grad).all().item() for p in model.parameters()), 'Nonfinite gradient')
        optimizer.step()
        require(all(torch.isfinite(p).all().item() for p in model.parameters()), 'Nonfinite parameter')
        n=len(batch['input_ids']); seen+=n; steps+=1
        total_sum+=float(total.detach())*n; risk_sum+=float(risk.detach())*n; type_sum+=float(types.detach())*n
        for j in range(8):
            unweighted[j]+=diagnostic['types_unweighted'][j]*n
            weighted[j]+=diagnostic['types_weighted'][j]*n
        if progress is not None and (steps==1 or steps%8==0 or steps==len(loader)):
            progress(dict(epoch=epoch,batch=steps,batches=len(loader),optimizer_steps=step_offset+steps,
                          samples=seen,loss=float(total.detach()),mean_loss=total_sum/seen,
                          elapsed_seconds=time.monotonic()-start,resources=resources()))
    require(seen>0, 'Empty training loader')
    return dict(epoch=epoch,optimizer_steps=step_offset+steps,epoch_steps=steps,samples=seen,
                train_loss=total_sum/seen,risk_loss=risk_sum/seen,type_loss=type_sum/seen,
                per_type_unweighted=dict(zip(LABELS,[v/seen for v in unweighted])),
                per_type_weighted=dict(zip(LABELS,[v/seen for v in weighted])),elapsed_seconds=time.monotonic()-start)


def state_inventory(model):
    return {k:dict(shape=list(v.shape),dtype=str(v.dtype),sha256=hashlib.sha256(v.detach().cpu().contiguous().numpy().tobytes()).hexdigest())
            for k,v in model.state_dict().items()}


def run_lite(manifest_path, *, run_id, regression_receipt, purpose='internal_experiment',data_mode='reviewed'):
    require(purpose=='internal_experiment', 'Unapproved legacy model cannot enter production/formal training')
    require(isinstance(run_id,str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{2,63}',run_id), 'Safe new run ID required')
    path=inside(RUNS/run_id,RUNS)
    require(not path.exists(), 'Never overwrite/retry an existing run')
    config,train,val,old_val,bindings,res=preflight(manifest_path,regression_receipt,data_mode=data_mode)
    bootstrap()
    from risk_speech_ai.training import set_training_seed,TrainingConfig,_metadata
    from risk_speech_ai.dataset import RiskSpeechDataset,make_training_dataloader
    import torch
    torch.set_num_threads(2)
    set_training_seed(42)
    model,tok,parent_metadata,parent_manifest=load_v2_start()
    initial_state=state_inventory(model)
    model.encoder.gradient_checkpointing_enable()
    optimizer=new_optimizer(model)
    loader=make_training_dataloader(RiskSpeechDataset(train.samples(),tokenizer=tok),tokenizer=tok,batch_size=8,seed=42,shuffle=True)
    require(len(loader)==106, 'Expected 106 updates per epoch')
    path.mkdir(parents=True,exist_ok=False)
    cfg=TrainingConfig(data_version='v3-lite-'+data_mode+'-inherited-v2-provisional',learning_rate=5e-6,
                       batch_size=8,epochs=2,seed=42,weight_decay=.01,model_revision=REVISION,tokenizer_revision=REVISION)
    metadata=_metadata(model,tok,cfg,torch.device('cpu'))
    lineage=dict(artifact_kind='research_model',training_authorized=True,parent_sha256=PARENT_SHA,
                 parent_bindings=parent_manifest['bindings'],parent_policy=dict(human_approved=False,label_status='provisional',source_kind='llm_synthetic'),
                 optimizer_reset=True,seed=42,bindings=bindings,config_sha256=digest(config),code_sha256=digest(code_inventory()),
                 manifest_sha256=sha(manifest_path),purpose='internal_experiment',human_approved=False,deployment_approved=False,
                 data_mode=data_mode,source_kind='llm_synthetic',human_reviewed=False,approved_for_production=False,
                 deployment_allowed=False,training_authorization_scope='internal_research_only',created_at=datetime.now(timezone.utc).isoformat())
    baseline=evaluate_split(model,tok,val); old_baseline=evaluate_split(model,tok,old_val)
    # Baselines, data/code/config, gates and budgets are saved BEFORE any update.
    create_json(path/'frozen_before_training.json',dict(config=config,lineage=lineage,resources=res,
                baseline=baseline,old_validation_baseline=old_baseline,initial_tensors=initial_state),root=RUNS)
    require(sha(manifest_path)==lineage['manifest_sha256'], 'Manifest changed during baseline')
    # Re-read all data/evidence and checks, to bind the training batch already compiled.
    if data_mode=='research_synthetic_v3':
        from .research_data import load_research_inputs
        _,_,_,current_bindings=load_research_inputs(manifest_path)
    else:
        _,_,_,current_bindings=load_training_inputs(manifest_path)
    require(current_bindings==bindings and digest(code_inventory())==lineage['code_sha256'], 'Inputs/code changed before first update')
    history=[]; references=[]; adopted=None
    def progress(record):
        record['time_utc']=datetime.now(timezone.utc).isoformat()
        with (path/'progress.jsonl').open('a',encoding='utf-8') as f:
            f.write(json.dumps(record,ensure_ascii=False)+'\n'); f.flush()
        print(json.dumps(record,ensure_ascii=False),flush=True)
    for epoch in (1,2):
        record=train_one_epoch(model,loader,optimizer,epoch=epoch,step_offset=(epoch-1)*106,progress=progress)
        history.append(record)
        tensors=state_inventory(model)
        changed=[k for k,v in tensors.items() if v['sha256']!=initial_state[k]['sha256']]
        record['changed_tensors_from_parent']=len(changed)
        record['changed_groups']={group:sum(k.startswith(group) for k in changed) for group in ['encoder.','risk_classifier.','type_classifier.']}
        require(all(record['changed_groups'].values()),'Encoder and both heads must actually update')
        candidate=evaluate_split(model,tok,val); old_candidate=evaluate_split(model,tok,old_val)
        gate=apply_gates(baseline['metrics'],candidate['metrics'],old_baseline['metrics'],old_candidate['metrics'],epoch=epoch)
        ref=save_v3_checkpoint(path/f'epoch_{epoch:03d}.pt',model,optimizer,metadata=metadata,lineage=lineage,epoch=epoch,history=history)
        references.append(ref)
        loaded=load_v3_state(ref['path'],model,ref['sha256'],tokenizer=tok)
        del loaded
        samples=val.samples()[:8]
        replay=runtime().raw_logits(model,tok,[(s.history_texts,s.current_text) for s in samples])
        replay_delta=max(abs(a-b) for x,y in zip(replay,candidate['logits'][:8]) for a,b in zip(x,y))
        require(replay_delta<=1e-6, 'Saved checkpoint CPU replay differs')
        create_json(path/f'epoch_{epoch:03d}_evaluation.json',dict(training=record,validation=candidate,old_validation=old_candidate,
            gates=gate,cpu_checkpoint_replay_max_abs_difference=replay_delta,
            tensor_inventory=tensors,uncertainty=family_paired_uncertainty(val,baseline,candidate)),root=RUNS)
        print('EPOCH_COMPLETE',json.dumps(dict(training=record,gates=gate,checkpoint=ref)),flush=True)
        verify_parent()
        if gate['adopt']:
            adopted=ref
            break
        if not gate['allow_epoch2']:
            break
    result=dict(status='RESEARCH_CANDIDATE_SELECTED' if adopted else 'NO_IMPROVEMENT_CANDIDATE_ADOPTED',
                history=history,checkpoints=references,selected=adopted,training_executed=True,final_generalization_confirmed=False,
                inherited_unreviewed_synthetic_v2=True,human_approved=False,deployment_approved=False)
    create_json(path/'run.json',result,root=RUNS)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',required=True); p.add_argument('--run-id',required=True); p.add_argument('--regression-receipt',required=True)
    p.add_argument('--data-mode',choices=['reviewed','research_synthetic_v3'],default='reviewed')
    args=p.parse_args()
    print(run_lite(args.manifest,run_id=args.run_id,regression_receipt=args.regression_receipt,data_mode=args.data_mode))
