"""Export a validated trained checkpoint into a lossless portable inference bundle."""
from __future__ import annotations
import argparse
import gc
import json
import os
from pathlib import Path
import shutil
from .src.common import BUNDLE,LABELS,PARENT_SHA,RUNS,V3,create_json,inside,read_json,require,sha


def package(run_path):
    import torch
    run_path=inside(run_path,RUNS)
    r=read_json(run_path/'run.json')
    require(r.get('training_executed') is True and r.get('checkpoints'),'No actual trained checkpoint')
    selected=r.get('selected') or r['checkpoints'][-1]
    path=inside(selected['path'],RUNS)
    require(sha(path)==selected['sha256'],'Training checkpoint changed')
    data=torch.load(path,map_location='cpu',weights_only=True,mmap=True)
    require(data['v3_lite_metadata']['parent_sha256']==PARENT_SHA and data['step_count']>0,'Missing real update lineage')
    out=V3/'handoff/research_20261117_v1';out.mkdir(parents=True,exist_ok=False)
    (out/'models').mkdir()
    for folder in ['vendor','tokenizer']:shutil.copytree(BUNDLE/folder,out/folder,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    shutil.copyfile(BUNDLE/'stage5_runtime.py',out/'core_runtime.py')
    shutil.copyfile(V3/'portable_runtime.py',out/'runtime.py')
    shutil.copyfile(BUNDLE/'requirements-tested.txt',out/'requirements-tested.txt')
    payload={k:data[k] for k in ['checkpoint_schema_version','model_state_dict','training_config','label_order','base_model','metadata',
                                 'v3_lite_metadata','epoch','step_count','sample_count']}
    payload.update(optimizer_state_dict={},inference_only=True)
    pending=out/'models/v3_seed42_inference.pt.partial'; dest=pending.with_suffix('')
    with pending.open('xb') as f:torch.save(payload,f);f.flush();os.fsync(f.fileno())
    check=torch.load(pending,map_location='cpu',weights_only=True,mmap=True)
    require(all(torch.equal(v,check['model_state_dict'][k]) for k,v in data['model_state_dict'].items()),'Inference export changed weights')
    del check;gc.collect();os.rename(pending,dest)
    inference=dict(path='models/v3_seed42_inference.pt',sha256=sha(dest),bytes=dest.stat().st_size)
    support=[dict(path=p.relative_to(out).as_posix(),sha256=sha(p)) for p in sorted(out.rglob('*')) if p.is_file() and p!=dest]
    m=dict(schema='v3-lite-inference-bundle/1',purpose='internal_experiment',source_kind='llm_synthetic',human_reviewed=False,
           approved_for_production=False,deployment_allowed=False,parent_sha256=PARENT_SHA,label_order=list(LABELS),thresholds=[.5]*9,
           seed=42,epoch=data['epoch'],optimizer_steps=data['step_count'],validation_adopted=r.get('selected') is not None,
           model=inference,support_files=support,revision=data['metadata']['model_revision'])
    create_json(out/'bundle_manifest.json',m)
    create_json(out/'CHECKPOINTS.json',dict(training_checkpoints=r['checkpoints'],inference=inference,
        inference_optimizer_buffers_excluded=True,training_bytes=path.stat().st_size,inference_bytes=dest.stat().st_size,
        tensor_count=len(data['model_state_dict']),tensor_contract={k:dict(shape=list(v.shape),dtype=str(v.dtype)) for k,v in data['model_state_dict'].items()},
        actual_trained=True,validation_adopted=m['validation_adopted'],bundle_manifest_sha256=sha(out/'bundle_manifest.json')))
    print(json.dumps(dict(bundle=str(out),manifest_sha256=sha(out/'bundle_manifest.json'),model=inference,training_bytes=path.stat().st_size),indent=2))
    return out


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',type=Path,required=True)
    package(p.parse_args().run)
