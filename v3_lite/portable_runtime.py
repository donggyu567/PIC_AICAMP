"""Portable v3 research inference. No repository, training data, or TEST access."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'vendor'))
import core_runtime as core
from risk_speech_ai.labels import LABELS


class V3Predictor:
    def __init__(self,bundle=HERE,*,expected_manifest_sha):
        import torch
        from transformers import AutoTokenizer
        self.bundle=Path(bundle).resolve()
        core.require(core.sha(self.bundle/'bundle_manifest.json')==expected_manifest_sha,'Trusted manifest SHA mismatch')
        m=core.read(self.bundle/'bundle_manifest.json')
        core.require(m['schema']=='v3-lite-inference-bundle/1' and m['label_order']==list(LABELS) and
                     m['thresholds']==[.5]*9 and m['purpose']=='internal_experiment' and
                     m['human_reviewed'] is False and m['deployment_allowed'] is False,'Invalid research bundle')
        for spec in m['support_files']:core.relative_file(self.bundle,spec)
        self.tokenizer=AutoTokenizer.from_pretrained(str(self.bundle/'tokenizer'),local_files_only=True)
        path=core.relative_file(self.bundle,m['model'])
        envelope=torch.load(path,map_location='cpu',weights_only=True,mmap=True)
        ext=envelope.get('v3_lite_metadata',{})
        core.require(envelope.get('inference_only') is True and envelope.get('optimizer_state_dict')=={} and
                     ext.get('schema')=='v3-lite-checkpoint/1' and ext.get('parent_sha256')==m['parent_sha256'] and
                     ext.get('epoch')==m['epoch'] and ext.get('human_reviewed') is False,'Invalid v3 inference lineage')
        del envelope
        # Core strict metadata/config/tokenizer/state reconstruction is shared with v2;
        # legacy=True skips only the v2-specific B_ratio/epoch3 extension assertion.
        # The separate v3 lineage was checked above, and is never claimed to be v2.
        self.model,self.metadata=core.load_model(path,m['model']['sha256'],self.tokenizer,legacy=True)
        self.manifest=m

    def predict(self,request):
        history,current=core.validate_request(request)
        z=core.raw_logits(self.model,self.tokenizer,[(history,current)])[0]
        response=core.output_response(z,[.5]*9,seed=42,model_sha=self.manifest['model']['sha256'])
        response['result'].update(model_version='KoELECTRA-v3-Lite-research',epoch=self.manifest['epoch'],
            threshold_version='v3-lite-fixed-0.5',human_reviewed=False,deployment_allowed=False,
            validation_adopted=self.manifest['validation_adopted'])
        return response


def serve_request(predictor,request):
    return core.serve_request(predictor,request)


if __name__=='__main__':
    import torch
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bundle',type=Path,default=HERE); p.add_argument('--manifest-sha',required=True)
    args=p.parse_args();torch.set_num_threads(2)
    predictor=V3Predictor(args.bundle,expected_manifest_sha=args.manifest_sha)
    for line in sys.stdin:
        try: request=json.loads(line)
        except (json.JSONDecodeError,UnicodeError):
            print(json.dumps(dict(ok=False,status='error',http_status=400,result=None,error={'code':'INVALID_JSON'})),flush=True)
            continue
        print(json.dumps(serve_request(predictor,request),ensure_ascii=False),flush=True)
