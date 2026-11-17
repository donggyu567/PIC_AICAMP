"""Record checks only. This module never invokes real research training."""
from __future__ import annotations

import argparse
import io
import json
from pathlib import Path
import platform
import subprocess
import sys
import time
import unittest

from .src.common import ROOT,V3,V2,BUNDLE,LABELS,PARENT_SHA,bootstrap,create_json,digest,inside,read_json,require,sha
from .src.train import code_inventory,new_optimizer,resources


def regression(out):
    stream=io.StringIO()
    suite=unittest.defaultTestLoader.discover(str(V3/'tests'),top_level_dir=str(ROOT))
    start=time.monotonic()
    result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    text=stream.getvalue()
    print(text,flush=True)
    (out/'regression.log').write_text(text,encoding='utf-8')
    record=dict(schema='v3-lite-regression/1',status='PASS' if result.wasSuccessful() and not result.skipped else 'FAIL',
                tests_run=result.testsRun,failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),
                elapsed_seconds=time.monotonic()-start,code_sha256=digest(code_inventory()),code_inventory=code_inventory(),
                command=f'"{sys.executable}" -B -X utf8 -m v3_lite.check_phase2 regression --output "{out}"',
                scope='Tiny automated unit fixtures only. Simulated review objects are in-memory assertions, not human approval evidence.',
                research_training_executed=False)
    create_json(out/'regression.json',record)
    require(record['status']=='PASS','Regression failed; real training remains blocked')
    return record


def parent_smoke(out):
    import torch
    from .src.checkpoint import load_v2_start,runtime,verify_parent
    bootstrap()
    torch.set_num_threads(2)
    res_before=resources()
    start=time.monotonic()
    model,tok,metadata,manifest=load_v2_start()
    path=BUNDLE/manifest['models']['42']['path']
    source=torch.load(path,map_location='cpu',weights_only=True,mmap=True)
    state=model.state_dict(); parent_state=source['model_state_dict']
    require(set(state)==set(parent_state),'Parent state keys changed')
    equal=all(torch.equal(value,parent_state[k]) for k,value in state.items())
    independent=all(value.data_ptr()!=parent_state[k].data_ptr() for k,value in model.named_parameters())
    require(equal and independent,'Warm-start parameters not equal/independent')
    optimizer=new_optimizer(model)
    optimizer_state_entries=len(optimizer.state)
    del source,parent_state,optimizer
    inputs=[([], '공개 안내문을 읽고 예약 일정을 정하겠습니다.'),
            (['도서관 안내 데스크에 문의했습니다.'], '자료실 운영 시간이 궁금합니다.'),
            (['문서 발급 창구에 신청했습니다.','접수 번호를 확인했습니다.'], '수령 예정일을 알려 주세요.')]
    module=runtime(); model.eval()
    a=module.raw_logits(model,tok,inputs)
    b=module.raw_logits(model,tok,inputs)
    delta=max(abs(x-y) for r,s in zip(a,b) for x,y in zip(r,s))
    require(delta<=1e-6,'CPU inference is not repeatable')
    verify_parent()
    record=dict(status='PASS',scope='Actual v2 parent SHA/strict restore/all tensors/CPU inference; no optimizer step or model save',
                parent_path=str(path),parent_sha256=PARENT_SHA,parent_sha_verified_before_and_after=True,
                state_tensors_checked=len(state),all_state_values_exactly_equal=equal,parameter_storages_independent=independent,
                optimizer_initialized='fresh AdamW lr5e-6 weight_decay0.01',optimizer_state_entries=optimizer_state_entries,
                optimizer_updates=0,input_count=3,repeat_inference_max_abs_difference=delta,logits=a,
                label_order=list(LABELS),input_contract=metadata['input_contract'],resources_before=res_before,
                resources_after=resources(),elapsed_seconds=time.monotonic()-start,
                python=sys.version,executable=sys.executable,torch_version=str(torch.__version__),
                command=f'"{sys.executable}" -B -X utf8 -m v3_lite.check_phase2 parent-smoke --output "{out}"',
                no_accuracy_claim=True,new_validation_evaluated=False,v3_checkpoint_created=False)
    create_json(out/'parent_smoke.json',record)
    print(json.dumps({k:v for k,v in record.items() if k not in ['logits','input_contract']},ensure_ascii=False,indent=2),flush=True)
    return record


def preservation(out):
    before=read_json(out/'preservation_before.json')
    changed=[name for name,stat in before['files'].items() if not (ROOT/name).is_file() or
             [(ROOT/name).stat().st_size,(ROOT/name).stat().st_mtime_ns]!=stat]
    root_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    v2_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=V2,text=True).strip()
    require(not changed and root_head==before['root_head'] and v2_head==before['v2_head'],'Preexisting files/HEAD changed')
    phase1_hashes=read_json(V3/'phase1_20261117_v1/required_sources_sha256.json')
    hash_changes=[name for name,h in phase1_hashes.items() if sha(V2/name)!=h]
    require(not hash_changes,'Existing required v2 documents changed')
    record=dict(status='PASS',preexisting_metadata_files_checked=len(before['files']),metadata_changes=changed,
                root_head=root_head,v2_head=v2_head,head_changed=False,required_v2_document_hash_changes=hash_changes,
                test_contents_or_ciphertext_opened=False,release_or_single_execution_records_opened=False,
                scope='Recorded file sizes/mtimes and HEAD; source hashes via bootstrap and parent SHA via smoke. Sealed TEST content deliberately not hashed.')
    create_json(out/'preservation.json',record)
    print(json.dumps(record,ensure_ascii=False,indent=2))
    return record


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode',choices=['regression','parent-smoke','preservation'])
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args(); out=inside(args.output,V3/'reports')
    require(out.is_dir(),'Use an existing fresh phase-two report directory')
    {'regression':regression,'parent-smoke':parent_smoke,'preservation':preservation}[args.mode](out)
