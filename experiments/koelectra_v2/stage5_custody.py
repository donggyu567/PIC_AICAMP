"""Custodian-only, one-time fixed-plan evaluation. Missing approval denies before TEST IO.

Neither approval nor evaluation is invoked by preparation. No ACL changes or
plaintext TEST files are performed. Approval attestation is separate from label review.
"""
from __future__ import annotations
import argparse
import csv
from datetime import datetime,timezone,timedelta
import gc
import hashlib
import json
from pathlib import Path
import subprocess

from expanded_common import ROOT,LABELS,SEEDS,read,sha,digest,require,write_json
from stage3_data import BASE,validate
from stage5_prepare import PLAN,REPORT


def identity():
    lines=subprocess.check_output(['whoami','/user','/fo','csv','/nh'],text=True,errors='replace')
    account,sid=list(csv.reader(lines.strip().splitlines()))[0]
    return account,sid


def validate_plan(path):
    p=read(path)
    require(p['schema']=='research-sealed-evaluation-plan/1','Wrong plan schema')
    require(p['primary_candidate']=='B_ratio' and p['comparison_arm']=='A_epoch' and p['seeds']==list(SEEDS),'Plan model family changed')
    require(p['thresholds']==[.5]*9 and p['epoch']==3 and p['label_order']==list(LABELS),'Frozen inference settings changed')
    require(p['human_approved'] is False and p['deployment_approved'] is False,'Research plan must remain unapproved for production')
    from stage5_prepare import STAGE4
    selection=read(STAGE4/'frozen_selection.json')
    require(sha(STAGE4/'frozen_selection.json')==p['stage4_selection_sha256'],'Original selection changed')
    require(p['bindings']==selection['bindings'] and p['models']=={a:selection['checkpoints'][a] for a in ['B_ratio','A_epoch']},'Plan changes frozen model references')
    for name,h in p['evaluation_code'].items():require(sha(ROOT/name)==h,'Evaluation code differs from frozen plan')
    require(digest(p['evaluation_code'])==p['code_sha256'],'Code manifest digest mismatch')
    require(sha(BASE/'test_seal_receipt.json')==p['test_receipt_sha256'],'Sealing receipt changed')
    return p


def validate_approval(release,*,plan_sha,receipt_sha,custodian_sid,now):
    require(release.get('schema')=='custodian-explicit-test-release/1','Wrong explicit release schema')
    require(release.get('approved_action')=='one_time_fixed_plan_test_evaluation','Missing explicit one-time evaluation approval')
    require(release.get('plan_sha256')==plan_sha and release.get('receipt_sha256')==receipt_sha,'Release not bound to fixed plan and TEST')
    require(release.get('custodian_sid')==custodian_sid,'Release custodian mismatch')
    require(isinstance(release.get('approval_reference'),str) and release['approval_reference'].strip(),'Real explicit approval reference required')
    stamp=datetime.fromisoformat(release['approved_at']);expires=datetime.fromisoformat(release['expires_at'])
    require(stamp.tzinfo is not None and expires.tzinfo is not None and stamp<=now<=expires and expires-stamp<=timedelta(hours=24),'Release time window invalid')
    require(release['human_label_review_complete'] is False and release['deployment_approved'] is False,'TEST access is not label/deployment approval')


def gate(plan_path,release_path):
    require(release_path is not None,'WAITING_EXPLICIT_CUSTODIAN_APPROVAL; TEST remains sealed')
    plan=validate_plan(plan_path);receipt=read(BASE/'test_seal_receipt.json')
    account,sid=identity()
    require(sid==receipt['custodian_sid'] and 'codexsandbox' not in account.lower(),'Actual custodian Windows context required')
    vault=Path(receipt['vault_path']).parent.resolve();release_path=Path(release_path).resolve()
    require(release_path.is_relative_to(vault),'Release must be stored under custodian-only vault ACL')
    release=read(release_path)
    validate_approval(release,plan_sha=sha(plan_path),receipt_sha=sha(BASE/'test_seal_receipt.json'),
        custodian_sid=sid,now=datetime.now(timezone.utc))
    return plan,receipt,release,vault


def issue_release(plan_path,reference,acknowledge):
    require(acknowledge and isinstance(reference,str) and reference.strip(),'Separate explicit custodian approval is required; this command is not preparation')
    plan=validate_plan(plan_path);receipt=read(BASE/'test_seal_receipt.json');account,sid=identity()
    require(sid==receipt['custodian_sid'] and 'codexsandbox' not in account.lower(),'Actual custodian context required')
    now=datetime.now(timezone.utc);path=Path(receipt['vault_path']).parent/f"release_{sha(plan_path)[:16]}.json"
    write_json(path,dict(schema='custodian-explicit-test-release/1',approved_action='one_time_fixed_plan_test_evaluation',
        plan_sha256=sha(plan_path),receipt_sha256=sha(BASE/'test_seal_receipt.json'),custodian_sid=sid,windows_account=account,
        approval_reference=reference,approved_at=now.isoformat(),expires_at=(now+timedelta(hours=24)).isoformat(),
        approval_record_type='operator attestation referencing an actual explicit approval; Windows account alone is not proof of human label review',
        human_label_review_complete=False,deployment_approved=False))
    print('EXPLICIT RELEASE RECORDED',path)


def reserve_once(vault,plan_sha,release_sha):
    # Fixed per-vault filename, not per model/seed/plan: the whole comparison runs once.
    path=Path(vault)/'phase5_evaluation_once.json'
    write_json(path,dict(schema='one-time-evaluation-claim/1',plan_sha256=plan_sha,release_sha256=release_sha,
        claimed_at=datetime.now(timezone.utc).isoformat(),retry_allowed=False,
        note='Failure consumes this claim; any recovery requires a separately documented custodian decision, never a blind retry'))
    return path


def decrypt(payload):
    from stage3_seal import dpapi
    return dpapi(payload,check=True)


def family_bootstrap(rows,logits_by_arm,thresholds,*,repetitions=2000,seed=20261110):
    import numpy as np
    from expanded_evaluation import probabilities,targets
    y=targets(rows);families=sorted({r['scenario_family_id'] for r in rows})
    groups={f:[i for i,r in enumerate(rows) if r['scenario_family_id']==f] for f in families}
    predictions={a:np.asarray([probabilities(v)>=thresholds for v in seeds.values()]) for a,seeds in logits_by_arm.items()}
    rng=np.random.default_rng(seed);values={a:[[] for _ in range(9)] for a in predictions};deltas={a:[] for a in predictions if a!='B_ratio'}
    for _ in range(repetitions):
        ids=[i for f in rng.choice(families,len(families),replace=True) for i in groups[f]]
        actual=y[ids].astype(bool);supports=actual.sum(0);current={}
        for arm,p in predictions.items():
            subset=p[:,ids,:];tp=(subset & actual).sum(1);fp=(subset & ~actual).sum(1);fn=(~subset & actual).sum(1)
            denom=2*tp+fp+fn;f1=np.divide(2*tp,denom,out=np.zeros_like(tp,dtype=float),where=denom!=0).mean(0)
            current[arm]=f1
            for j,v in enumerate(f1):
                if supports[j]>0:values[arm][j].append(float(v))
        if supports[0]>0:
            for arm in deltas:deltas[arm].append(float(current['B_ratio'][0]-current[arm][0]))
    def summary(v):return dict(valid_repetitions=len(v),ci95=np.percentile(v,[2.5,97.5]).tolist() if v else None)
    return dict(unit='scenario_family_id',families=len(families),repetitions=repetitions,seed=seed,
        note='Registered families equal conversations in this corpus; semantic independence unverified. Seed-mean metrics, not probability ensembling.',
        by_arm={a:dict(zip(['risk']+list(LABELS),[summary(x) for x in v])) for a,v in values.items()},
        paired_binary_f1_delta_B_minus_comparator={a:summary(v) for a,v in deltas.items()},
        missing_positive_support_policy='skip resample for that output')


def evaluate(plan_path,release_path):
    # All approval checks precede ciphertext opening or decrypting.
    plan,receipt,release,vault=gate(plan_path,release_path)
    from stage5_runtime import load_model,raw_logits
    from expanded_assets import load_tokenizer
    from expanded_evaluation import evaluate_logits,seed_summary
    import torch
    torch.set_num_threads(2);tok=load_tokenizer()
    # Check all frozen public model references before consuming one-time authorization.
    for arm,models in plan['models'].items():
        for s,ref in models.items():require(sha(ref['path'])==ref['sha256'],'Model file changed')
    if plan['v1']['status']=='COMPATIBLE':require(sha(plan['v1']['checkpoint']['path'])==plan['v1']['checkpoint']['sha256'],'v1 file changed')
    claim=reserve_once(vault,sha(plan_path),sha(release_path))
    try:
        cipher=Path(receipt['vault_path']).read_bytes()
        require(hashlib.sha256(cipher).hexdigest()==receipt['ciphertext_sha256'],'Sealed cipher hash mismatch')
        plain=decrypt(cipher)
        require(hashlib.sha256(plain).hexdigest()==receipt['payload_sha256'],'Sealed plaintext payload hash mismatch')
        payload=json.loads(plain);records=payload['conversations'];validate(records,expected=40)
        members=[dict(conversation_id=c['conversation_id'],scenario_family_id=c['scenario_family_id'],role=c['split']) for c in records]
        require(members==receipt['split_membership'] and all(c['split']=='test' for c in records),'TEST membership mismatch')
        from stage3_data import stats
        require(stats(records)==receipt['stats'],'Sealed TEST support differs from receipt')
        rows=[];inputs=[]
        for c in records:
            normal=not any(u['is_phishing'] for u in c['utterances'])
            for i,u in enumerate(c['utterances']):
                rows.append(dict(u,conversation_id=c['conversation_id'],scenario_family_id=c['scenario_family_id'],source_id='PROJECT_AI_GENERATED',hard_negative=normal))
                inputs.append(([x['text'] for x in c['utterances'][max(0,i-5):i]],u['text']))
        results={};all_logits={}
        for arm,models in plan['models'].items():
            results[arm]={};all_logits[arm]={}
            for s,ref in models.items():
                model,_=load_model(ref['path'],ref['sha256'],tok,arm=arm,seed=int(s),bindings=plan['bindings'])
                logits=raw_logits(model,tok,inputs);all_logits[arm][int(s)]=logits
                metrics=evaluate_logits(rows,logits,plan['thresholds'])
                results[arm][int(s)]={k:v for k,v in metrics.items() if k not in ('errors','groups')}
                del model;gc.collect()
        if plan['v1']['status']=='COMPATIBLE':
            ref=plan['v1']['checkpoint'];model,_=load_model(ref['path'],ref['sha256'],tok,legacy=True)
            logits=raw_logits(model,tok,inputs);metrics=evaluate_logits(rows,logits,[.5]*9)
            results['v1']={'single_checkpoint':{k:v for k,v in metrics.items() if k not in ('errors','groups')}}
            all_logits['v1']={'single_checkpoint':logits};del model;gc.collect()
        b=plan['bootstrap']
        uncertainty=family_bootstrap(rows,all_logits,plan['thresholds'],repetitions=b['repetitions'],seed=b['seed'])
        output=dict(schema='one-time-exploratory-test-results/1',plan_sha256=sha(plan_path),release_sha256=sha(release_path),
            claim_sha256=sha(claim),evaluation_performed=True,results=results,
            seed_summaries={a:seed_summary(results[a]) for a in ['B_ratio','A_epoch']},uncertainty=uncertainty,
            test_support=receipt['stats'],source_kind='llm_synthetic',label_status='provisional',human_label_review_complete=False,
            deployment_approved=False,model_selection_changed=False,thresholds=plan['thresholds'],retrained=False,
            v1_status=plan['v1']['status'],individual_gold_or_logits_exported=False)
        write_json(vault/'phase5_aggregate_results.json',output)
        del plain,payload,records,rows,inputs,all_logits
        print('ONE-TIME EVALUATION COMPLETE; AGGREGATES IN CUSTODIAN VAULT')
    except Exception as exc:
        # No exception strings or tracebacks containing test text are written.
        write_json(vault/'phase5_failure.json',dict(status='FAILED_CLAIM_CONSUMED',error_type=type(exc).__name__,plan_sha256=sha(plan_path),retry=False))
        raise RuntimeError('Evaluation failed; claim remains consumed. Custodian review required.') from None


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',choices=['issue-release','evaluate'])
    parser.add_argument('--plan',type=Path,default=PLAN);parser.add_argument('--release',type=Path)
    parser.add_argument('--approval-reference');parser.add_argument('--confirm-explicit-custodian-approval',action='store_true')
    args=parser.parse_args()
    if args.mode=='issue-release':issue_release(args.plan,args.approval_reference,args.confirm_explicit_custodian_approval)
    else:evaluate(args.plan,args.release)
