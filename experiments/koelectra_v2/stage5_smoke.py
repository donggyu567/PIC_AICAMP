"""Actual CPU inference on public VALIDATION only, including portable bundle and v1."""
from pathlib import Path
import gc
import json
import subprocess
import sys
import tempfile

from expanded_common import ROOT,SEEDS,read,sha,require,write_json
from stage3_data import BASE,jsonl
from stage5_prepare import REPORT,BUNDLE,STAGE4
from stage5_runtime import load_model,raw_logits


def main():
    import torch
    from expanded_assets import load_tokenizer
    torch.set_num_threads(2);tok=load_tokenizer()
    conv=jsonl(BASE/'validation_32_synthetic.jsonl')[0]
    inputs=[([u['text'] for u in conv['utterances'][max(0,i-5):i]],u['text']) for i,u in enumerate(conv['utterances'])]
    selection=read(STAGE4/'frozen_selection.json');records=[]
    for arm in ['B_ratio','A_epoch']:
        for seed in SEEDS:
            ref=selection['checkpoints'][arm][str(seed)]
            model,metadata=load_model(ref['path'],ref['sha256'],tok,arm=arm,seed=seed,bindings=selection['bindings'])
            actual=raw_logits(model,tok,inputs)
            saved=read(Path(ref['path']).parent/'validation_epoch_003.json')['logits'][:8]
            delta=max(abs(a-b) for row,target in zip(actual,saved) for a,b in zip(row,target))
            require(len(actual)==8 and delta<1e-4,'Actual CPU inference differs from saved validation logits')
            records.append(dict(arm=arm,seed=seed,checkpoint=ref,samples=8,max_logit_delta=delta,input_contract=metadata['input_contract']))
            del model;gc.collect();print('CPU_REPLAY_PASS',arm,seed,delta,flush=True)
    path=ROOT.parents[1]/'artifacts/risk_speech_ai/koelectra_risk_v1.pt'
    expected='1131f9dcc665f79073d98ecd6845573109a89e44dbf2917d299a8fea057020a7'
    try:
        model,metadata=load_model(path,expected,tok,legacy=True)
        logits=raw_logits(model,tok,inputs)
        v1=dict(status='COMPATIBLE',checkpoint=dict(path=str(path),sha256=expected),input_contract=metadata['input_contract'],
            model_revision=metadata['model_revision'],tokenizer_revision=metadata['tokenizer_revision'],samples=8,
            logits_shape=[len(logits),len(logits[0])],comparison_thresholds=[.5]*9,
            note='Same pinned pair preprocessing and tokenizer content/probes; single historical checkpoint, not three independent v1 seeds')
        del model;gc.collect()
    except Exception as exc:
        v1=dict(status='BLOCKED_INCOMPATIBLE',reason_type=type(exc).__name__,reason=str(exc),checkpoint=dict(path=str(path),sha256=expected))
    # A fresh process outside the repository must load bundled vendor code and tokenizer.
    with tempfile.TemporaryDirectory() as work:
        code="import sys,json,pathlib;sys.path.insert(0,sys.argv[1]);from stage5_runtime import ResearchPredictor,serve_request; import torch;torch.set_num_threads(2);p=ResearchPredictor(sys.argv[1],42,expected_manifest_sha=sys.argv[2]);a=serve_request(p,{'history_texts':[],'current_text':'공식 안내문을 제가 직접 확인하겠습니다.'});b=serve_request(p,{'current_text':''});c=serve_request(p,{'current_text':'가 '*1200});import risk_speech_ai.model as mod;assert pathlib.Path(mod.__file__).resolve().is_relative_to(pathlib.Path(sys.argv[1])/'vendor');assert a['ok'] and a['result']['human_approved'] is False and not b['ok'] and b['error']['code']=='INVALID_REQUEST' and not c['ok'] and c['error']['code']=='INPUT_TOO_LONG'; print(json.dumps({'success':a,'invalid_request':b,'overlong_current':c,'vendor_path':mod.__file__},ensure_ascii=False))"
        p=subprocess.run([sys.executable,'-B','-X','utf8','-c',code,str(BUNDLE),sha(BUNDLE/'bundle_manifest.json')],cwd=work,capture_output=True,encoding='utf-8')
        require(p.returncode==0,'Portable bundle smoke failed: '+p.stderr[-2000:])
        portable=json.loads(p.stdout.splitlines()[-1])
    write_json(REPORT/'smoke.json',dict(status='PASS',selected_checkpoints=records,v1=v1,portable_bundle=portable,
        test_access=False,model_training=False,approval_state='research_only_unreviewed'))
    print('PORTABLE BUNDLE PASS; V1',v1['status'],flush=True)


if __name__=='__main__':main()
