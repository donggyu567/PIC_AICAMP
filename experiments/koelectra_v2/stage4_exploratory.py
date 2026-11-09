"""Explicit, unapproved-label exploratory training; no TEST reader or production gate bypass.

Reuses stage-2 losses, initialization, runtime compiler, metrics and pinned PR35
training/data code. A new checkpoint/selection schema keeps these artifacts out
of the formally approved production executor.
"""
from __future__ import annotations
import argparse
from collections import Counter
import ctypes
from ctypes import wintypes
from dataclasses import asdict
import gc
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import traceback

from expanded_common import ROOT, LABELS, REVISION, MODEL, SEEDS, PROTOCOL_SHA, require, read, sha, digest, publish, write_json, compile_runtime
from stage3_data import BASE, REPORT as STAGE3, AUTHORED, jsonl, validate, OLD_TRAIN
from stage3_research import load_research

OUT = ROOT/'artifacts/v2_exploratory_runs/stage4_20261109_v1'
REPORT = ROOT/'reports/v2_stage4_20261109_v1'
POLICY = dict(schema='exploratory-training-policy/1', mode='exploratory_training', purpose='internal_experiment',
    source_kind='llm_synthetic', label_status='provisional', human_review_complete=False,
    human_approved=False, deployment_approved=False, production_training_authorized=False,
    authorization_basis='Explicit user phase-4 instruction permits internally generated synthetic research inputs; this is not human label review',
    original_protocol_sha256=PROTOCOL_SHA,
    differences_from_formal_protocol=['TRAIN80 synthetic research set instead of rights-unverified original v1 TRAIN',
        'Validation32 is unreviewed synthetic: exploratory evaluation only',
        'Separate research checkpoint/selection schema; no fabricated approval hashes',
        'CPU FP32 with encoder gradient checkpointing for memory; batch8 and original optimizer/hyperparameters',
        'A0 is the actual first-epoch snapshot of the same unweighted fresh-public trajectory, not a separately retrained copy'])


def resources():
    class Memory(ctypes.Structure):
        _fields_ = [('length',wintypes.DWORD),('load',wintypes.DWORD)] + [(k,ctypes.c_ulonglong) for k in
            ('physical_total','physical_available','commit_limit','commit_available','virtual_total','virtual_available','extended')]
    mem = Memory(); mem.length = ctypes.sizeof(mem)
    require(ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(mem)), 'Cannot inspect memory headroom')
    return dict(cpu_count=os.cpu_count(), disk_free=shutil.disk_usage(ROOT).free,
        **{k:getattr(mem,k) for k,_ in mem._fields_ if k not in ('length','extended')})


def event(path, **item):
    with Path(path).open('a', encoding='utf-8') as f:
        f.write(json.dumps(dict(time_utc=__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(), **item), ensure_ascii=False)+'\n')
        f.flush()


def code_inventory():
    files = sorted((ROOT/'experiments/koelectra_v2').glob('*.py')) + sorted((ROOT/'artifacts/v1_reference/pr35_9bab7e383928/risk_speech_ai').glob('*.py'))
    return {p.relative_to(ROOT).as_posix():sha(p) for p in files}


def blocked_arms():
    return dict(C_approved=dict(status='BLOCKED', reason='No separately approved additional synthetic TRAIN partition; do not relabel provisional TRAIN80 as approved'),
        B_step_matched=dict(status='BLOCKED', reason='Approved C augmentation count and C update budget are undefined'),
        formal_original_v1_arms=dict(status='BLOCKED', reason='Original v1 source use rights/evidence and formal approvals are absent; research A/B below explicitly use synthetic TRAIN80'))


def precheck():
    require(read(STAGE3/'tests.json')['status'] == 'PASS', 'Stage3 regression incomplete')
    require(read(STAGE3/'preservation.json')['status'] == 'PASS', 'Stage3 preservation incomplete')
    require(read(STAGE3/'cpu_dataloader.json')['status'] == 'PASS', 'Stage3 CPU incomplete')
    train = load_research('train', mode='internal_experiment')
    val = load_research('validation', mode='internal_experiment')
    data = read(BASE/'data_use_manifest.json'); split = read(BASE/'split_manifest.json')
    receipt = read(BASE/'test_seal_receipt.json')
    require(receipt['sealed'] and receipt['phase5_release_required'] and receipt['stats']['conversations'] == 40, 'TEST sealing incomplete')
    require(sha(BASE/'test_seal_receipt.json') == split['test_receipt_sha256'], 'Receipt binding changed')
    require(split['train_sha256'] == train.data_sha256 and split['validation_sha256'] == val.data_sha256, 'Split data hash mismatch')
    require(not list(AUTHORED.glob('test_*.txt')), 'TEST plaintext remains')
    try:
        with Path(receipt['vault_path']).open('rb'): pass
    except PermissionError: pass
    else: raise ValueError('Development account can open TEST vault')
    members = split['members']
    require(Counter(m['role'] for m in members) == Counter(train=80,validation=32,test=40), 'Split counts mismatch')
    for key in ['conversation_id','scenario_family_id']:
        require(len({m[key] for m in members}) == 152, 'Split identity collision')
    # Only project-generated simulations are allowed. Historical v1 never enters rows.
    canonical = jsonl(ROOT/'dataset/04. processed/v2_pilot/pilot_canonical.jsonl')
    require(len(canonical) == 16 and all(c['is_synthetic'] is True and c['actual_call'] is False and
        c['source_kind'] == 'llm_simulation' for c in canonical), 'Legacy16 generation basis is unconfirmed')
    convs = {role:jsonl(BASE/data[role]['path']) for role in ['train','validation']}
    for role, records in convs.items():
        validate(records, expected=80 if role=='train' else 32)
        require(all(c['actual_call'] is False and c['source_kind'] == 'llm_synthetic' and
            c.get('human_review_complete',False) is False and c['deployment_approved'] is False for c in records), 'Unverified source/approval')
    require(all(c['source_kind'] == 'llm_simulation' and c['actual_call'] is False and c['generation_model'] == 'GPT-6 (Codex)'
        for c in jsonl(OLD_TRAIN)[16:]), 'Legacy8 generation basis missing')
    bindings = dict(train_sha256=train.data_sha256, validation_sha256=val.data_sha256,
        data_manifest_sha256=sha(BASE/'data_use_manifest.json'), split_sha256=sha(BASE/'split_manifest.json'),
        test_receipt_sha256=sha(BASE/'test_seal_receipt.json'),
        generation_history_sha256=sha(BASE/'generation_history.json'), stage3_quality_sha256=sha(STAGE3/'quality.json'))
    return train,val,convs,bindings


def capture():
    paths = []
    for args in [['git','ls-files','-z'], ['git','ls-files','--others','--exclude-standard','-z']]:
        paths += subprocess.check_output(args,cwd=ROOT).decode().split('\0')
    before = {p:sha(ROOT/p) for p in paths if p and not p.startswith(('reports/v2_stage4_', 'artifacts/v2_exploratory_runs/', 'experiments/koelectra_v2/stage4_', 'tests/test_stage4_'))}
    write_json(REPORT/'preservation_before.json', dict(files=before, head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        git_status=subprocess.check_output(['git','status','--short'],cwd=ROOT,text=True)))


def setup():
    require(not OUT.exists() and not REPORT.exists(), 'Use a new version namespace; never overwrite existing runs')
    REPORT.mkdir(parents=True,exist_ok=False)
    capture()
    train,val,convs,bindings = precheck()
    hardware = resources()
    write_json(REPORT/'stage3_verification.json', dict(status='PASS', train_conversations=80, train_utterances=len(train.samples),
        validation_conversations=32,validation_utterances=len(val.samples),test_conversations=40,test_sealed=True,
        test_body_access=False, bindings=bindings, v1_included=False, original_aux_validation_used=False,
        semantic_independence='UNVERIFIED', actual_label_accuracy='PROVISIONAL', hardware=hardware))
    write_json(REPORT/'data_use_policy.json', dict(**POLICY, bindings=bindings,
        source_evidence=dict(legacy16_canonical_sha256=sha(ROOT/'dataset/04. processed/v2_pilot/pilot_canonical.jsonl'),
            legacy8_generation_registry_sha256=sha(ROOT/'dataset/04. processed/v2_train_expansion/generation_and_scenarios.json'),
            stage3_generation_registry_sha256=sha(BASE/'generation_history.json'))))
    write_json(REPORT/'blocked_experiments.json', blocked_arms())
    # Free commit, unlike currently available physical RAM, includes Windows paging.
    require(hardware['commit_available'] >= 4*1024**3, 'Insufficient Windows commit headroom for full FP32 model/AdamW')
    require(hardware['disk_free'] >= 32*1024**3, 'Insufficient space for 18 full optimizer checkpoints')
    OUT.mkdir(parents=True,exist_ok=False)
    inventory = code_inventory()
    write_json(OUT/'execution_manifest.json', dict(**POLICY, bindings=bindings, code=inventory,
        code_sha256=digest(inventory), seeds=list(SEEDS), public_model=MODEL, revision=REVISION,
        public_encoder_sha256='f3f249cc07826bc2964a2c0dbbd0d239df4fe55efc03ba33e1bd1584cf56c566',
        batch_size=8, learning_rate=2e-5,weight_decay=.01,optimizer='AdamW',precision='float32',
        cpu_threads=2, gradient_checkpointing=True, epochs=[1,2,3], hardware=hardware,
        evaluation_scope='validation_exploratory_only', test_access=False))
    print('SETUP PASS', hardware, flush=True)


def weights_from_rows(rows):
    counts = [sum(label in r['labels'] for r in rows) for label in LABELS]
    return [min(10.,max(1.,(len(rows)-p)/p)) if p else 1. for p in counts]


def flatten(conversations):
    return [dict(u, conversation_id=c['conversation_id'],scenario_family_id=c['scenario_family_id'],
        source_id='PROJECT_AI_GENERATED',hard_negative=not any(x['is_phishing'] for x in c['utterances']))
        for c in conversations for u in c['utterances']]


def research_config(arm,seed):
    require(arm in ('A_epoch','B_ratio') and seed in SEEDS, 'Unsupported exploratory trajectory')
    return dict(schema='exploratory-runtime/1', mode='exploratory_training',
        stage2_runtime=compile_runtime(arm,seed), policy_sha256=digest(POLICY), gradient_checkpointing=True,
        train_role='synthetic_research_train80', evaluation_scope='validation_exploratory_only')


def infer(model,tok,samples):
    import torch
    from risk_speech_ai.dataset import RiskSpeechDataset, make_training_dataloader
    loader = make_training_dataloader(RiskSpeechDataset(samples,tokenizer=tok),tokenizer=tok,batch_size=8,shuffle=False)
    values=[]; model.eval()
    with torch.inference_mode():
        for batch in loader:
            output=model(**{k:batch[k] for k in ['input_ids','attention_mask','token_type_ids']})
            values.extend(torch.cat([output.risk_logits,output.type_logits],dim=1).tolist())
    require(len(values)==len(samples), 'Inference sample alignment failed')
    return values


def train(arm,seed):
    import torch
    from expanded_assets import fresh_public_model, load_tokenizer
    from expanded_training import losses
    from expanded_evaluation import evaluate_logits
    from risk_speech_ai.dataset import RiskSpeechDataset, make_training_dataloader
    from risk_speech_ai.training import TrainingConfig, _metadata
    trainset,val,convs,bindings=precheck()
    manifest=read(OUT/'execution_manifest.json')
    require(bindings==manifest['bindings'] and digest(code_inventory())==manifest['code_sha256'], 'Inputs/code changed after execution registration')
    config=research_config(arm,seed)
    path=OUT/arm/f'seed_{seed}'; path.mkdir(parents=True,exist_ok=False)
    torch.set_num_threads(2); torch.set_num_interop_threads(1)
    tok=load_tokenizer()
    before=resources(); start=time.monotonic()
    event(path/'progress.jsonl',state='initializing',resources=before)
    model=fresh_public_model(seed).cpu()
    model.encoder.gradient_checkpointing_enable()
    initial_heads=digest({n:t.tolist() for n,t in model.state_dict().items() if n.startswith(('risk_classifier.','type_classifier.'))})
    cfg=TrainingConfig(data_version='stage4-exploratory-synthetic80-provisional',epochs=3,seed=seed,batch_size=8,
        learning_rate=2e-5,weight_decay=.01,model_revision=REVISION,tokenizer_revision=REVISION)
    metadata=_metadata(model,tok,cfg,torch.device('cpu'))
    loader=make_training_dataloader(RiskSpeechDataset(trainset.samples,tokenizer=tok),tokenizer=tok,batch_size=8,seed=seed,shuffle=True)
    trainrows=flatten(convs['train']); valrows=flatten(convs['validation'])
    weights=[1.]*8 if arm=='A_epoch' else weights_from_rows(trainrows)
    optimizer=torch.optim.AdamW(model.parameters(),lr=2e-5,weight_decay=.01,foreach=False)
    history=[]; references=[]; steps=0
    write_json(path/'initialization.json',dict(seed=seed,initial_heads_sha256=initial_heads,public_encoder_sha256=manifest['public_encoder_sha256'],
        runtime=config,weights=weights,bindings=bindings,metadata=metadata,policy=POLICY,parameter_count=sum(p.numel() for p in model.parameters())))
    for epoch in (1,2,3):
        model.train(); total_sum=risk_sum=type_sum=0.; seen=0; epoch_start=time.monotonic()
        for b,batch in enumerate(loader,1):
            optimizer.zero_grad(set_to_none=True)
            output=model(**{k:batch[k] for k in ['input_ids','attention_mask','token_type_ids']})
            total,risk,types=losses(output,batch['risk_target'],batch['type_targets'],weights)
            total.backward()
            require(all(p.grad is None or torch.isfinite(p.grad).all().item() for p in model.parameters()), 'Nonfinite gradient')
            optimizer.step()
            require(all(torch.isfinite(p).all().item() for p in model.parameters()), 'Nonfinite parameter')
            steps+=1; n=len(batch['input_ids']); seen+=n
            total_sum+=float(total.detach())*n; risk_sum+=float(risk.detach())*n; type_sum+=float(types.detach())*n
            if b==1 or b%10==0 or b==len(loader):
                record=dict(state='training',arm=arm,seed=seed,epoch=epoch,batch=b,batches=len(loader),steps=steps,
                    loss=float(total.detach()),mean_loss=total_sum/seen,elapsed_seconds=time.monotonic()-start)
                event(path/'progress.jsonl',**record); print(json.dumps(record),flush=True)
        logits=infer(model,tok,val.samples)
        metrics=evaluate_logits(valrows,logits,[.5]*9)
        record=dict(epoch=epoch,optimizer_steps=steps,train_loss=total_sum/seen,risk_loss=risk_sum/seen,type_loss=type_sum/seen,
            validation_binary_f1=metrics['binary']['f1'],elapsed_seconds=time.monotonic()-epoch_start)
        history.append(record)
        ext=dict(schema='exploratory-checkpoint/1',policy=POLICY,runtime=config,arm=arm,seed=seed,epoch=epoch,
            optimizer_steps=steps,bindings=bindings,code_sha256=manifest['code_sha256'],weights=weights,thresholds=[.5]*9,
            threshold_version='fixed-0.5',initial_heads_sha256=initial_heads,initial_encoder_sha256=manifest['public_encoder_sha256'],
            evaluation_scope='unreviewed_synthetic_validation_exploratory',test_access=False)
        payload=dict(checkpoint_schema_version='v1',model_state_dict=model.state_dict(),optimizer_state_dict=optimizer.state_dict(),
            epoch=epoch,training_config=asdict(cfg),label_order=list(LABELS),base_model=metadata['base_model'],metadata=metadata,
            epoch_losses=history,sample_count=len(trainset.samples),step_count=steps,exploratory_metadata=ext)
        target=path/f'epoch_{epoch:03d}.pt'
        publish(target,lambda stream:torch.save(payload,stream))
        ref=dict(path=str(target),sha256=sha(target)); references.append(ref)
        write_json(target.with_suffix('.json'),dict(**ref,exploratory_metadata=ext))
        write_json(path/f'epoch_{epoch:03d}_metrics.json',dict(training=record,validation=metrics,evaluation_scope='exploratory'))
        write_json(path/f'validation_epoch_{epoch:03d}.json',dict(schema='exploratory-predictions/1',role='validation',seed=seed,epoch=epoch,
            arm=arm,bindings=bindings,row_keys=[f'{s.conversation_id}:{s.utterance_id}' for s in val.samples],logits=logits,checkpoint=ref))
        event(path/'progress.jsonl',state='epoch_saved',**record,checkpoint=ref)
        print('EPOCH_SAVED',arm,seed,epoch,record['train_loss'],metrics['binary']['f1'],flush=True)
    best=min(range(3),key=lambda i:(-round(history[i]['validation_binary_f1'],12),i))
    for name,index in [('best',best),('last',2)]:
        os.link(references[index]['path'],path/f'{name}.pt')
        write_json(path/f'{name}.json',dict(checkpoint=references[index],epoch=index+1,selection_scope='per_seed_provisional_validation'))
    write_json(path/'run.json',dict(status='COMPLETE',arm=arm,seed=seed,history=history,references=references,
        best_epoch=best+1,last_epoch=3,optimizer_steps=steps,initial_heads_sha256=initial_heads,weights=weights,
        elapsed_seconds=time.monotonic()-start,policy=POLICY))
    if arm=='A_epoch':
        alias=OUT/'A0'/f'seed_{seed}'; alias.mkdir(parents=True,exist_ok=False)
        for name in ['epoch_001','best','last']: os.link(references[0]['path'],alias/f'{name}.pt')
        write_json(alias/'run.json',dict(status='COMPLETE_SNAPSHOT',arm='A0',seed=seed,best_epoch=1,last_epoch=1,optimizer_steps=82,
            checkpoint=references[0],history=history[:1],policy=POLICY,
            note='Actual first epoch of same fresh-public unweighted trajectory; no independent duplicate training'))


def validate_prediction(p,seed,epoch,arm,bindings,keys):
    require(p['schema']=='exploratory-predictions/1' and p['role']=='validation' and p['arm']==arm and
        p['seed']==seed and p['epoch']==epoch and p['bindings']==bindings and p['row_keys']==keys,'Prediction provenance mismatch')
    require(sha(p['checkpoint']['path'])==p['checkpoint']['sha256'],'Checkpoint changed')


def mean_defined(values):
    values=[v for v in values if v is not None]
    return sum(values)/len(values) if values else None


def summarize():
    import numpy as np
    from expanded_evaluation import evaluate_logits, probabilities, targets
    from expanded_selection import GRID
    from risk_speech_ai.metrics import binary_metrics
    _,val,convs,bindings=precheck(); rows=flatten(convs['validation'])
    keys=[f'{s.conversation_id}:{s.utterance_id}' for s in val.samples]
    selected={}; predictions={}; selection_scores={}
    for arm in ['A_epoch','B_ratio']:
        predictions[arm]={}
        for epoch in [1,2,3]:
            predictions[arm][epoch]={}
            for seed in SEEDS:
                p=read(OUT/arm/f'seed_{seed}'/f'validation_epoch_{epoch:03d}.json')
                validate_prediction(p,seed,epoch,arm,bindings,keys)
                predictions[arm][epoch][seed]=p
        scores={e:float(np.mean([evaluate_logits(rows,predictions[arm][e][s]['logits'])['binary']['f1'] for s in SEEDS])) for e in [1,2,3]}
        selection_scores[arm]=scores
        selected[arm]=min(scores,key=lambda e:(-round(scores[e],12),e))
    y=targets(rows); bp={s:probabilities(predictions['B_ratio'][selected['B_ratio']][s]['logits']) for s in SEEDS}
    thresholds=[]; support=[]
    for i in range(9):
        positive=int(y[:,i].sum()); negative=len(y)-positive
        families=len({r['conversation_id'] for j,r in enumerate(rows) if y[j,i]})
        eligible=positive>=10 and negative>=10 and families>=3
        if eligible:
            scores={t:float(np.mean([binary_metrics(y[:,i],bp[s][:,i],t)['f1'] for s in SEEDS])) for t in GRID}
            chosen=min(GRID,key=lambda t:(-round(scores[t],12),round(abs(t-.5),12),-t))
        else: chosen=.5
        thresholds.append(chosen); support.append(dict(positive=positive,negative=negative,positive_conversations=families,tuned=eligible))
    bundle=dict(schema='exploratory-frozen-selection/1',policy=POLICY,bindings=bindings,selection_source='validation',
        epoch_by_arm=selected,mean_seed_epoch_f1=selection_scores,thresholds=thresholds,threshold_support=support,
        threshold_version='exploratory-validation-grid-v1',checkpoints={},test_access=False)
    results={}
    for arm,source,epoch,ts in [('A0','A_epoch',1,[.5]*9),('A_epoch','A_epoch',selected['A_epoch'],[.5]*9),
        ('B_ratio','B_ratio',selected['B_ratio'],[.5]*9),('B_threshold','B_ratio',selected['B_ratio'],thresholds)]:
        perseed={s:evaluate_logits(rows,predictions[source][epoch][s]['logits'],ts) for s in SEEDS}
        bundle['checkpoints'][arm]={str(s):predictions[source][epoch][s]['checkpoint'] for s in SEEDS}
        results[arm]=dict(epoch=epoch,thresholds=ts,per_seed=perseed,
            means=dict(binary={k:mean_defined([m['binary'][k] for m in perseed.values()]) for k in ['precision','recall','f1','average_precision']},
                normal_conversation_false_alert_rate=mean_defined([m['conversations']['normal_false_alert_rate'] for m in perseed.values()]),
                per_type={l:{k:mean_defined([m['per_type'][l][k] for m in perseed.values()]) for k in ['precision','recall','f1','average_precision']} for l in LABELS}),
            mean_policy='Average defined seed values only; see per_seed undefined_reasons for unsupported precision')
    write_json(REPORT/'frozen_selection.json',bundle)
    write_json(REPORT/'comparison.json',dict(schema='exploratory-comparison/1',policy=POLICY,bindings=bindings,results=results,
        blocked=blocked_arms(),test_access=False,evaluation_scope='validation_selected_and_scored_same_unreviewed_synthetic_set; optimistic_not_final'))
    write_json(REPORT/'phase5_readiness.json',dict(schema='exploratory-phase5-handoff/1',final_test_opened=False,
        selection=dict(path=str(REPORT/'frozen_selection.json'),sha256=sha(REPORT/'frozen_selection.json')),
        models=bundle['checkpoints'],test_receipt_sha256=bindings['test_receipt_sha256'],human_approved=False,deployment_approved=False,
        production_final_cli_compatible=False,required=['Explicit phase5 custodian release and DPAPI decryption outside development context',
        'Exploratory-specific checkpoint reader/evaluator preserving unreviewed provenance; never pass as production-approved model',
        'Hash verification and frozen selection; no further TEST-driven tuning']))
    print('COMPARISON COMPLETE',selected,thresholds,flush=True)


def preserve():
    before=read(REPORT/'preservation_before.json')
    changed=[p for p,h in before['files'].items() if sha(ROOT/p)!=h]
    require(not changed,'Preexisting files changed')
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    require(head==before['head'],'Git HEAD changed')
    weights=read(ROOT/'reports/v2_stage1_20261109/inventory.json')['local_weight_inventory']
    require(all(sha(ROOT.parents[1]/w['root']/w['path'])==w['sha256'] for w in weights),'Original weights changed')
    write_json(REPORT/'preservation.json',dict(status='PASS',files=len(before['files']),changed=changed,weight_files=len(weights),head=head))


def execute():
    setup()
    outcomes=[]
    for seed in SEEDS:
        for arm in ['A_epoch','B_ratio']:
            p=subprocess.Popen([sys.executable,'-B','-X','utf8',__file__,'train','--arm',arm,'--seed',str(seed)],cwd=ROOT)
            code=p.wait()
            outcomes.append(dict(arm=arm,seed=seed,exit_code=code))
            if code:
                write_json(REPORT/'execution_failure.json',dict(status='INCOMPLETE',outcomes=outcomes,
                    reason='Real training subprocess failed; no automatic unlimited retry',performance_fabricated=False))
                return code
    summarize(); preserve()
    write_json(REPORT/'execution_complete.json',dict(status='COMPLETE_EXPLORATORY',outcomes=outcomes,test_opened=False,policy=POLICY))
    return 0


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=['execute','setup','train','summarize','preserve'])
    parser.add_argument('--arm',choices=['A_epoch','B_ratio'])
    parser.add_argument('--seed',type=int,choices=SEEDS)
    args=parser.parse_args()
    try:
        if args.mode=='execute': raise SystemExit(execute())
        elif args.mode=='train': train(args.arm,args.seed)
        else: globals()[args.mode]()
    except Exception as exc:
        traceback.print_exc()
        if REPORT.exists():
            destination=REPORT/f'error_{time.time_ns()}.json'
            write_json(destination,dict(status='ERROR',mode=args.mode,error_type=type(exc).__name__,error=str(exc),traceback=traceback.format_exc()))
        raise SystemExit(2)
