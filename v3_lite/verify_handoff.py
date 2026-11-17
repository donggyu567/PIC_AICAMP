"""Fresh-process standalone probe, including lossless training/inference parity."""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()


def probe(bundle,training,training_sha,output,parent_inventory=None):
    import torch
    torch.set_num_threads(2)
    sys.dont_write_bytecode=True
    bundle=Path(bundle).resolve();sys.path.insert(0,str(bundle))
    spec=importlib.util.spec_from_file_location('v3_runtime_probe',bundle/'runtime.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    manifest_sha=sha(bundle/'bundle_manifest.json')
    predictor=module.V3Predictor(bundle,expected_manifest_sha=manifest_sha)
    inputs=[([], '문서 수령 방법을 확인하고 방문 시간을 정하겠습니다.'),
            (['제가 직접 예약 창구에 문의했습니다.'],'예약자 성함은 [PERSON]입니다.'),
            (['신청하지 않은 연락인데 왜 인증을 요구하시나요?'],'제가 받은 인증번호를 읽으라는 뜻인가요?')]
    logits=module.core.raw_logits(predictor.model,predictor.tokenizer,inputs)
    repeat=module.core.raw_logits(predictor.model,predictor.tokenizer,inputs)
    repeat_delta=max(abs(a-b) for x,y in zip(logits,repeat) for a,b in zip(x,y))
    responses=[module.serve_request(predictor,dict(history_texts=h,current_text=c)) for h,c in inputs]
    single_logits=[module.core.raw_logits(predictor.model,predictor.tokenizer,[item])[0] for item in inputs]
    batch_single_delta=max(abs(a-b) for x,y in zip(logits,single_logits) for a,b in zip(x,y))
    for z,r in zip(single_logits,responses):
        assert r['ok'] and 0<=r['result']['risk_probability']<=1 and 0<=r['result']['risk_score']<=100
        assert len(r['result']['type_probabilities'])==8
        p=1/(1+math.exp(-z[0]));assert abs(p-r['result']['risk_probability'])<1e-12
        assert abs(100*p-r['result']['risk_score'])<1e-10
        for j,label in enumerate(module.LABELS,1):assert abs(1/(1+math.exp(-z[j]))-r['result']['type_probabilities'][label])<1e-12
    invalid=[module.serve_request(predictor,x) for x in [None,{'current_text':''},{'current_text':'안내','extra':1},{'history_texts':'wrong','current_text':'안내'}]]
    assert all(r['http_status']==400 and not r['ok'] and r['result'] is None for r in invalid)
    over=module.serve_request(predictor,{'current_text':'확인 '*800})
    assert over['http_status']==422 and not over['ok']
    absent=module.serve_request(None,{'current_text':'안내'});assert absent['http_status']==503
    # Reuse the loaded model object to compare training weights, avoiding two
    # full encoder copies on the8GB host. Both sources are independently hashed.
    assert sha(training)==training_sha
    payload=torch.load(training,map_location='cpu',weights_only=True,mmap=True)
    inference_state=predictor.model.state_dict()
    equal=all(torch.equal(v,payload['model_state_dict'][k]) for k,v in inference_state.items())
    assert equal
    changes=None
    if parent_inventory:
        initial=json.loads(Path(parent_inventory).read_text(encoding='utf-8'))['initial_tensors']
        changed=[k for k,v in payload['model_state_dict'].items() if hashlib.sha256(v.detach().contiguous().numpy().tobytes()).hexdigest()!=initial[k]['sha256']]
        changes=dict(total=len(changed),groups={g:sum(k.startswith(g) for k in changed) for g in ['encoder.','risk_classifier.','type_classifier.']})
        assert all(changes['groups'].values())
    predictor.model.load_state_dict(payload['model_state_dict'],strict=True)
    predictor.model.eval()
    training_logits=module.core.raw_logits(predictor.model,predictor.tokenizer,inputs)
    parity=max(abs(a-b) for x,y in zip(logits,training_logits) for a,b in zip(x,y))
    assert repeat_delta==0 and parity<=1e-6
    record=dict(status='PASS',fresh_process=True,bundle=str(bundle),manifest_sha256=manifest_sha,
                inference_sha256=predictor.manifest['model']['sha256'],training_sha256=training_sha,
                tensor_count=len(inference_state),all_training_inference_tensors_equal=equal,
                independently_verified_changes_from_frozen_parent=changes,
                training_inference_max_abs_logit_difference=parity,repeat_max_abs_difference=repeat_delta,
                batch_vs_single_logit_max_difference=batch_single_delta,single_sigmoid_matches_same_batching=True,
                cpu_inputs=3,responses=responses,invalid_request_statuses=[r['http_status'] for r in invalid],
                overlength_status=over['http_status'],not_ready_status=absent['http_status'],
                schema_labels_tokenizer_single_sigmoid_checked=True,accuracy_claim=False,
                v2_test_accessed=False,executable=sys.executable)
    with Path(output).open('x',encoding='utf-8') as f:json.dump(record,f,ensure_ascii=False,indent=2)
    print(json.dumps({k:v for k,v in record.items() if k!='responses'},ensure_ascii=False,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bundle',required=True);p.add_argument('--training',required=True);p.add_argument('--training-sha',required=True);p.add_argument('--output',required=True)
    p.add_argument('--parent-inventory')
    a=p.parse_args();probe(a.bundle,a.training,a.training_sha,a.output,a.parent_inventory)
