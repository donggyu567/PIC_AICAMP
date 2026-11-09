"""Verify finished exploratory runs and prepare immutable research handoff, no TEST IO."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import gc
import math
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import sys

from expanded_common import ROOT,LABELS,SEEDS,MODEL,REVISION,REFERENCE,read,sha,digest,require,write_json,publish
from stage3_data import BASE,jsonl,REPORT as STAGE3

STAGE4=ROOT/'reports/v2_stage4_20261109_v1'
RUNS=ROOT/'artifacts/v2_exploratory_runs/stage4_20261109_v1'
REPORT=ROOT/'reports/v2_stage5_20261110_v1'
BUNDLE=ROOT/'artifacts/v2_research_handoff/stage5_20261110_v1'
PLAN=REPORT/'frozen_evaluation_plan.json'


def snapshot():
    names=[]
    for args in [['git','ls-files','-z'],['git','ls-files','--others','--exclude-standard','-z']]:
        names+=subprocess.check_output(args,cwd=ROOT).decode().split('\0')
    names=[x for x in names if x and not x.startswith(('reports/v2_stage5_','artifacts/v2_research_handoff/',
        'experiments/koelectra_v2/stage5_','tests/test_stage5_'))]
    # Actual model weights have independent inventory entries; other old files remain byte-bound.
    old={x:sha(ROOT/x) for x in names if not x.endswith('.pt')}
    write_json(REPORT/'preservation_before.json',dict(files=old,head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        git_status=subprocess.check_output(['git','status','--short'],cwd=ROOT,text=True)))


def verify():
    import torch
    import numpy as np
    from expanded_evaluation import evaluate_logits,probabilities,targets
    from expanded_selection import GRID
    from risk_speech_ai.checkpoint import validate_checkpoint_metadata
    from risk_speech_ai.metrics import binary_metrics
    torch.set_num_threads(2)
    require(not REPORT.exists(),'Use a new version; never replace existing verification')
    REPORT.mkdir(parents=True);snapshot()
    complete=read(STAGE4/'execution_complete.json');selection=read(STAGE4/'frozen_selection.json')
    comparison=read(STAGE4/'comparison.json');handoff=read(STAGE4/'phase5_readiness.json')
    require(complete['status']=='COMPLETE_EXPLORATORY' and complete['checkpoint_files']==18,'Stage4 not complete')
    require(sha(STAGE4/'COMPLETE.md')==complete['complete_report_sha256'],'Stage4 report changed')
    require(sha(STAGE4/'checkpoint_verification.json')==complete['checkpoint_verification_sha256'],'Stage4 checkpoint audit changed')
    require(handoff['selection']['sha256']==sha(STAGE4/'frozen_selection.json'),'Selection receipt mismatch')
    require(read(STAGE4/'preservation.json')['status']=='PASS','Stage4 preservation failed')
    bindings=selection['bindings'];require(comparison['bindings']==bindings,'Comparison data differs')
    source=read(RUNS/'execution_manifest.json')
    require(source['bindings']==bindings,'Training manifest bindings mismatch')
    for name,h in source['code'].items():
        require(sha(RUNS/'source_snapshot'/name)==h and sha(ROOT/name)==h,'Training source changed')
    data_specs=dict(train_sha256=BASE/'train_80_candidate.jsonl',validation_sha256=BASE/'validation_32_synthetic.jsonl',
        data_manifest_sha256=BASE/'data_use_manifest.json',split_sha256=BASE/'split_manifest.json',
        test_receipt_sha256=BASE/'test_seal_receipt.json',generation_history_sha256=BASE/'generation_history.json',stage3_quality_sha256=STAGE3/'quality.json')
    for k,path in data_specs.items():require(sha(path)==bindings[k],'Data/receipt hash mismatch')
    convs=jsonl(BASE/'validation_32_synthetic.jsonl')
    rows=[dict(u,conversation_id=c['conversation_id'],scenario_family_id=c['scenario_family_id'],source_id='PROJECT_AI_GENERATED',
        hard_negative=not any(x['is_phishing'] for x in c['utterances'])) for c in convs for u in c['utterances']]
    keys=[f"{r['conversation_id']}:{r['utterance_id']}" for r in rows]
    inventory=[];all_predictions={};summaries={}
    for arm in ['A_epoch','B_ratio']:
        all_predictions[arm]={};scores={}
        for epoch in [1,2,3]:
            all_predictions[arm][epoch]={};f1s=[]
            for seed in SEEDS:
                folder=RUNS/arm/f'seed_{seed}'
                ref=read(folder/f'epoch_{epoch:03d}.json')
                require(sha(ref['path'])==ref['sha256'],'Actual model SHA mismatch')
                ckpt=torch.load(ref['path'],map_location='cpu',weights_only=True,mmap=True)
                validate_checkpoint_metadata(ckpt);ext=ckpt['exploratory_metadata']
                require(ext['bindings']==bindings and ext['code_sha256']==source['code_sha256'],'Checkpoint code/data binding mismatch')
                require((ext['arm'],ext['seed'],ext['epoch'],ckpt['step_count'])==(arm,seed,epoch,82*epoch),'Checkpoint identity mismatch')
                require(ext['policy']['human_approved'] is False and ext['policy']['deployment_approved'] is False,'False checkpoint approval')
                require(ckpt['metadata']['model_revision']==ckpt['metadata']['tokenizer_revision']==REVISION,'Revision mismatch')
                require(ckpt['optimizer_state_dict']['state'] and all(float(s['step'])==82*epoch for s in ckpt['optimizer_state_dict']['state'].values()),'Optimizer state mismatch')
                require(tuple(ckpt['model_state_dict']['risk_classifier.weight'].shape)==(1,768) and
                    tuple(ckpt['model_state_dict']['type_classifier.weight'].shape)==(8,768),'Wrong classifier shape')
                require(ext['thresholds']==[.5]*9,'Training thresholds changed')
                inventory.append(dict(arm=arm,seed=seed,epoch=epoch,path=ref['path'],sha256=ref['sha256'],bytes=Path(ref['path']).stat().st_size,
                    optimizer_steps=82*epoch,input_contract=ckpt['metadata']['input_contract']))
                p=read(folder/f'validation_epoch_{epoch:03d}.json')
                require(p['role']=='validation' and p['bindings']==bindings and p['row_keys']==keys and p['checkpoint']==dict(path=ref['path'],sha256=ref['sha256']),'Predictions/evidence mismatch')
                actual=evaluate_logits(rows,p['logits'],[.5]*9)
                saved=read(folder/f'epoch_{epoch:03d}_metrics.json')['validation']
                require(actual==saved,'Saved metrics differ from prediction replay')
                all_predictions[arm][epoch][seed]=p;f1s.append(actual['binary']['f1'])
                del ckpt;gc.collect()
                print('VERIFIED',arm,seed,epoch,flush=True)
            scores[epoch]=sum(f1s)/3
        chosen=min(scores,key=lambda e:(-round(scores[e],12),e))
        require(chosen==selection['epoch_by_arm'][arm],'Frozen epoch no longer matches registered selection rule')
        for epoch,value in scores.items():require(math.isclose(value,selection['mean_seed_epoch_f1'][arm][str(epoch)],abs_tol=1e-12),'Epoch selection scores differ')
        summaries[arm]=dict(epoch=chosen,binary={},per_type={})
        metrics=[evaluate_logits(rows,all_predictions[arm][chosen][s]['logits']) for s in SEEDS]
        for field in ['precision','recall','f1','average_precision','roc_auc']:
            vals=[m['binary'][field] for m in metrics if m['binary'][field] is not None]
            summaries[arm]['binary'][field]=dict(mean=statistics.mean(vals),std_sample=statistics.stdev(vals),values=vals)
        vals=[m['conversations']['normal_false_alert_rate'] for m in metrics]
        summaries[arm]['normal_false_alert_rate']=dict(mean=statistics.mean(vals),std_sample=statistics.stdev(vals),values=vals)
        for label in LABELS:
            summaries[arm]['per_type'][label]={}
            for field in ['precision','recall','f1','average_precision']:
                vals=[m['per_type'][label][field] for m in metrics if m['per_type'][label][field] is not None]
                summaries[arm]['per_type'][label][field]=dict(mean=statistics.mean(vals) if vals else None,
                    std_sample=statistics.stdev(vals) if len(vals)>1 else None,values=vals)
        for field in ['precision','recall','f1','average_precision']:
            require(math.isclose(summaries[arm]['binary'][field]['mean'],comparison['results'][arm]['means']['binary'][field],abs_tol=1e-12),'Comparison binary mean mismatch')
        for label in LABELS:
            for field in ['precision','recall','f1','average_precision']:
                a=summaries[arm]['per_type'][label][field]['mean'];b=comparison['results'][arm]['means']['per_type'][label][field]
                require(a==b or (a is not None and b is not None and math.isclose(a,b,abs_tol=1e-12)),'Comparison type mean mismatch')
    # Replay the exact original validation-only grid/tie rules, without saving a new selection.
    y=targets(rows);epoch=selection['epoch_by_arm']['B_ratio'];p={s:probabilities(all_predictions['B_ratio'][epoch][s]['logits']) for s in SEEDS}
    ts=[]
    for i in range(9):
        positive=int(y[:,i].sum());negative=len(y)-positive
        conversations=len({r['conversation_id'] for j,r in enumerate(rows) if y[j,i]})
        if positive>=10 and negative>=10 and conversations>=3:
            scores={t:sum(binary_metrics(y[:,i],p[s][:,i],t)['f1'] for s in SEEDS)/3 for t in GRID}
            chosen=min(GRID,key=lambda t:(-round(scores[t],12),round(abs(t-.5),12),-t))
        else:chosen=.5
        ts.append(chosen)
    require(ts==selection['thresholds']==[.5]*9,'Frozen thresholds differ from original selection')
    split=read(BASE/'split_manifest.json');members=split['members'];receipt=read(BASE/'test_seal_receipt.json')
    require(len(members)==152 and len({m['conversation_id'] for m in members})==len({m['scenario_family_id'] for m in members})==152,'Split metadata overlap')
    require([m for m in members if m['role']=='test']==receipt['split_membership'],'TEST split receipt mismatch')
    write_json(REPORT/'verification.json',dict(status='PASS',checkpoints=inventory,summary=summaries,bindings=bindings,
        original_selection_sha256=sha(STAGE4/'frozen_selection.json'),thresholds=ts,
        metrics_replayed_from_saved_validation_logits=True,test_body_read=False,model_training=False,
        test_release_approved=False,test_evaluation_status='WAITING_EXPLICIT_CUSTODIAN_APPROVAL',
        early_access_evidence=dict(stage4_logged_test_opened=False,known_preseal_cpu_structure_check=True,
            known_postseal_access_probes='denied per stage3/4 logs',full_os_audit_available=False,
            claim='Project records contain no TEST model inference; cannot prove absence of unlogged privileged access')))
    print('18 CHECKPOINTS AND SELECTION VERIFIED',flush=True)


def bundle():
    from expanded_assets import load_tokenizer
    require(read(REPORT/'verification.json')['status']=='PASS','Verify first')
    require(not BUNDLE.exists(),'Never overwrite a handoff bundle')
    BUNDLE.mkdir(parents=True)
    for path in REFERENCE.joinpath('risk_speech_ai').glob('*.py'):
        target=BUNDLE/'vendor/risk_speech_ai'/path.name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,target)
    shutil.copyfile(ROOT/'experiments/koelectra_v2/stage5_runtime.py',BUNDLE/'stage5_runtime.py')
    tok=load_tokenizer();tok.save_pretrained(str(BUNDLE/'tokenizer'))
    selection=read(STAGE4/'frozen_selection.json');models={}
    for seed in SEEDS:
        ref=selection['checkpoints']['B_ratio'][str(seed)]
        target=BUNDLE/f'models/B_ratio/seed_{seed}.pt';target.parent.mkdir(parents=True,exist_ok=True)
        os.link(ref['path'],target)
        models[str(seed)]=dict(path=target.relative_to(BUNDLE).as_posix(),sha256=ref['sha256'])
    support=[dict(path=p.relative_to(BUNDLE).as_posix(),sha256=sha(p)) for p in sorted(BUNDLE.rglob('*')) if p.is_file() and p.suffix!='.pt']
    write_json(BUNDLE/'bundle_manifest.json',dict(schema='research-server-bundle/1',purpose='internal_experiment',source_kind='llm_synthetic',
        human_approved=False,deployment_approved=False,label_status='provisional',models=models,default_seed=42,
        default_seed_basis='Existing stage2 CLI default 42 / lowest registered seed; not chosen by validation ranking',
        candidate_arm='B_ratio',epoch=3,label_order=list(LABELS),thresholds=selection['thresholds'],
        threshold_version=selection['threshold_version'],bindings=selection['bindings'],support_files=support,
        public_model=MODEL,model_revision=REVISION,tokenizer_revision=REVISION,
        original_selection_sha256=sha(STAGE4/'frozen_selection.json'),
        note='Checkpoint hard links preserve exact original bytes including optimizer state; transport by file copy into a new location'))
    dependencies()
    print('BUNDLE CREATED',BUNDLE,flush=True)


def dependencies():
    import importlib.metadata as md
    # Pinned PR35 metrics use NumPy, not scikit-learn. Record real installed runtime dependencies only.
    packages=['torch','transformers','tokenizers','numpy','safetensors','huggingface-hub']
    text='\n'.join(f'{p}=={md.version(p)}' for p in packages)+'\n'
    publish(BUNDLE/'requirements-tested.txt',lambda f:f.write(text.encode()))
    write_json(REPORT/'environment.json',dict(python=sys.version,direct_dependencies={p:md.version(p) for p in packages},
        metric_implementation='pinned PR35 risk_speech_ai.metrics (NumPy implementation)',
        preparation_correction='Removed an unnecessary scikit-learn dependency assumption after detecting it is not installed; no installation or model/data change'))


def freeze():
    require(read(REPORT/'smoke.json')['status']=='PASS','Actual inference smoke required')
    selection=read(STAGE4/'frozen_selection.json');verification=read(REPORT/'verification.json')
    smoke=read(REPORT/'smoke.json')
    files=sorted((ROOT/'experiments/koelectra_v2').glob('*.py'))+sorted((REFERENCE/'risk_speech_ai').glob('*.py'))
    code={p.relative_to(ROOT).as_posix():sha(p) for p in files}
    v1=smoke['v1']
    plan=dict(schema='research-sealed-evaluation-plan/1',purpose='internal_experiment',human_approved=False,deployment_approved=False,
        label_status='provisional',primary_candidate='B_ratio',comparison_arm='A_epoch',seeds=list(SEEDS),epoch=3,
        candidate_basis='User phase5 requests B_ratio family for type detection and normal-conversation false alerts; original preregistration selects epochs/thresholds per arm, not an across-arm winner',
        candidate_choice_preregistered=False,server_default_seed=42,server_seed_basis='Existing CLI default; evaluation retains all three seeds',
        thresholds=selection['thresholds'],threshold_version=selection['threshold_version'],label_order=list(LABELS),
        models={a:selection['checkpoints'][a] for a in ['B_ratio','A_epoch']},v1=v1,
        bindings=selection['bindings'],stage4_selection_sha256=sha(STAGE4/'frozen_selection.json'),
        bundle_manifest_sha256=sha(BUNDLE/'bundle_manifest.json'),
        evaluation_code=code,code_sha256=digest(code),
        bootstrap=dict(unit='scenario_family_id',repetitions=2000,seed=20261110,interval='percentile_95',
            scope='seed-mean binary/type F1 and paired binary F1 deltas; missing-support resamples skipped per output'),
        test_receipt_sha256=sha(BASE/'test_seal_receipt.json'),test_release_approved=False,
        test_evaluation_status='WAITING_EXPLICIT_CUSTODIAN_APPROVAL',
        release_policy='Actual custodian SID plus separately documented explicit approval bound to this plan hash and receipt; one vault claim across all models',
        plaintext_disk_files=False,outputs='aggregate metrics only inside custodian-protected vault; no per-row gold/logits',
        v1_comparison='same inputs and thresholds 0.5, one historical checkpoint; no fabricated multi-seed v1 results',
        model_selection_after_test=False,retraining_after_test=False)
    write_json(PLAN,plan)
    write_json(REPORT/'test_status.json',dict(status='WAITING_EXPLICIT_CUSTODIAN_APPROVAL',test_evaluation_performed=False,
        test_metrics=None,v1_same_test_comparison=None,plan_sha256=sha(PLAN),receipt_sha256=plan['test_receipt_sha256'],
        acl_changed=False,plaintext_test_read=False,custodian_approval_record_created=False))
    print('PLAN FROZEN; TEST STILL SEALED',sha(PLAN),flush=True)


def preserve():
    before=read(REPORT/'preservation_before.json')
    changed=[p for p,h in before['files'].items() if sha(ROOT/p)!=h]
    require(not changed,'Preexisting artifact changed')
    require(subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()==before['head'],'Git HEAD changed')
    inventory=read(REPORT/'verification.json')['checkpoints']
    require(all(sha(x['path'])==x['sha256'] for x in inventory),'Training checkpoints changed')
    weights=read(ROOT/'reports/v2_stage1_20261109/inventory.json')['local_weight_inventory']
    require(all(sha(ROOT.parents[1]/w['root']/w['path'])==w['sha256'] for w in weights),'v1/public weights changed')
    write_json(REPORT/'preservation.json',dict(status='PASS',preexisting_files=len(before['files']),stage4_weights=18,other_weights=len(weights),changed=[],head=before['head']))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=['verify','bundle','dependencies','freeze','preserve'])
    globals()[p.parse_args().mode]()
