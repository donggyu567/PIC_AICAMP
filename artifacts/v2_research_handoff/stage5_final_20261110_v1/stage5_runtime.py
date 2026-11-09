"""Portable research inference only. No training, TEST reader or production approval."""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
VENDOR=HERE/'vendor'
if VENDOR.is_dir(): sys.path.insert(0,str(VENDOR))
else: sys.path.insert(0,str(HERE.parents[1]/'artifacts/v1_reference/pr35_9bab7e383928'))

from risk_speech_ai.labels import LABELS


def require(ok,message):
    if not ok: raise ValueError(message)


def sha(path):
    value=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for part in iter(lambda:stream.read(1024*1024),b''): value.update(part)
    return value.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def relative_file(root,spec):
    root=Path(root).resolve(); name=spec['path']
    require(isinstance(name,str) and not Path(name).is_absolute() and ':' not in name and '\\' not in name,'Relative artifact path required')
    path=(root/name).resolve()
    require(path.is_relative_to(root) and path.is_file(),'Missing/escaping bundle artifact')
    require(sha(path)==spec['sha256'],'Bundle artifact SHA mismatch')
    return path


def compatible_tokenizer(metadata,tokenizer):
    from risk_speech_ai.checkpoint import tokenizer_metadata,tokenizer_behavior
    expected=dict(metadata['tokenizer_metadata']);actual=tokenizer_metadata(tokenizer)
    # Packaging changes storage location, not vocabulary or tokenization behavior.
    for field in ['name','resolved_revision']:
        expected.pop(field,None);actual.pop(field,None)
    require(expected==actual,'Tokenizer content/contract mismatch')
    require(metadata['tokenizer_behavior']==tokenizer_behavior(tokenizer),'Tokenizer probe mismatch')


def load_model(path,expected_sha,tokenizer,*,arm=None,seed=None,bindings=None,legacy=False):
    import torch
    from transformers import ElectraConfig,ElectraModel
    from risk_speech_ai.checkpoint import validate_checkpoint_metadata,validate_model_config
    from risk_speech_ai.model import RiskSpeechClassifier
    require(sha(path)==expected_sha,'Checkpoint SHA mismatch')
    checkpoint=torch.load(path,map_location='cpu',weights_only=True,mmap=True)
    metadata=validate_checkpoint_metadata(checkpoint)
    compatible_tokenizer(metadata,tokenizer)
    if not legacy:
        ext=checkpoint.get('exploratory_metadata',{})
        require(ext.get('schema')=='exploratory-checkpoint/1' and ext['arm']==arm and ext['seed']==seed and ext['epoch']==3,'Wrong frozen research checkpoint')
        require(ext['bindings']==bindings,'Checkpoint data bindings mismatch')
        require(ext['policy']['human_approved'] is False and ext['policy']['deployment_approved'] is False,'Research checkpoint approval mismatch')
    config=ElectraConfig.from_dict(metadata['encoder_config'])
    if metadata['encoder_config'].get('attn_implementation','absent') is None and 'attn_implementation' not in config.to_dict():
        config.attn_implementation=None
    with torch.device('meta'): model=RiskSpeechClassifier(ElectraModel(config))
    validate_model_config(metadata,model)
    model.load_state_dict(checkpoint['model_state_dict'],strict=True,assign=True)
    for module in model.modules():
        for name,tensor in list(module._buffers.items()):
            if tensor is not None and tensor.is_meta:
                require(name in ('position_ids','token_type_ids') and name in module._non_persistent_buffers_set,'Unexpected meta buffer')
                module._buffers[name]=(torch.arange(tensor.shape[-1],dtype=tensor.dtype).expand(tensor.shape).clone()
                    if name=='position_ids' else torch.zeros(tensor.shape,dtype=tensor.dtype))
    model.eval()
    return model,metadata


def raw_logits(model,tokenizer,inputs,*,batch_size=8):
    import torch
    from risk_speech_ai.tokenization import build_model_input
    values=[]
    for start in range(0,len(inputs),batch_size):
        features=[]
        for history,current in inputs[start:start+batch_size]:
            prepared=build_model_input(history,current,tokenizer=tokenizer)
            features.append({k:getattr(prepared,k) for k in ['input_ids','attention_mask','token_type_ids']})
        batch=tokenizer.pad(features,padding=True,return_tensors='pt')
        with torch.inference_mode():
            output=model(**{k:batch[k] for k in ['input_ids','attention_mask','token_type_ids']})
        joined=torch.cat([output.risk_logits,output.type_logits],dim=1)
        require(joined.shape==(len(features),9) and torch.isfinite(joined).all().item(),'Invalid model logits')
        values.extend(joined.tolist())
    return values


def validate_request(request):
    require(isinstance(request,dict) and set(request)<= {'history_texts','current_text'},'Unknown request fields')
    history=request.get('history_texts',[]);current=request.get('current_text')
    require(isinstance(history,list) and len(history)<=100 and all(isinstance(t,str) and t.strip() and len(t)<=32000 for t in history),'Invalid history_texts')
    require(isinstance(current,str) and current.strip() and len(current)<=32000,'Invalid current_text')
    return history,current


def output_response(values,thresholds,*,seed,model_sha):
    require(len(values)==9 and all(math.isfinite(v) for v in values),'Invalid logits')
    require(len(thresholds)==9 and all(type(v) in (float,int) and math.isfinite(v) and 0<=v<=1 for v in thresholds),'Invalid thresholds')
    p=[1/(1+math.exp(-v)) if v>=0 else math.exp(v)/(1+math.exp(v)) for v in values]
    return dict(ok=True,status='success',http_status=200,result=dict(risk_probability=p[0],risk_score=100*p[0],
        is_phishing=p[0]>=thresholds[0],type_probabilities=dict(zip(LABELS,p[1:])),
        detected_types=[l for i,l in enumerate(LABELS,1) if p[i]>=thresholds[i]],
        threshold_version='exploratory-validation-grid-v1',thresholds=thresholds,seed=seed,checkpoint_sha256=model_sha,
        purpose='internal_experiment',human_approved=False,deployment_approved=False),error=None)


class ResearchPredictor:
    def __init__(self,bundle=HERE,seed=42,*,expected_manifest_sha=None):
        from transformers import AutoTokenizer
        self.bundle=Path(bundle).resolve()
        require(isinstance(expected_manifest_sha,str) and sha(self.bundle/'bundle_manifest.json')==expected_manifest_sha,'Trusted bundle manifest SHA required')
        m=read(self.bundle/'bundle_manifest.json')
        require(m['schema']=='research-server-bundle/1' and m['deployment_approved'] is False and m['human_approved'] is False,'Not a research bundle')
        require(type(seed) is int and str(seed) in m['models'],'Unregistered seed')
        require(m['label_order']==list(LABELS) and m['thresholds']==[.5]*9,'Frozen inference contract changed')
        for item in m['support_files']:relative_file(self.bundle,item)
        self.tokenizer=AutoTokenizer.from_pretrained(str(self.bundle/'tokenizer'),local_files_only=True)
        spec=m['models'][str(seed)]
        path=relative_file(self.bundle,spec)
        self.model,self.metadata=load_model(path,spec['sha256'],self.tokenizer,arm='B_ratio',seed=seed,bindings=m['bindings'])
        self.thresholds=m['thresholds'];self.seed=seed;self.model_sha=spec['sha256']

    def predict(self,request):
        history,current=validate_request(request)
        return output_response(raw_logits(self.model,self.tokenizer,[(history,current)])[0],self.thresholds,seed=self.seed,model_sha=self.model_sha)


def serve_request(predictor,request):
    from risk_speech_ai.tokenization import InputTooLongError,TokenizerContractError
    def failure(code,status):return dict(ok=False,status='error',http_status=status,result=None,error=dict(code=code))
    if predictor is None:return failure('NOT_READY',503)
    try:validate_request(request)
    except ValueError:return failure('INVALID_REQUEST',400)
    try:return predictor.predict(request)
    except InputTooLongError:return failure('INPUT_TOO_LONG',422)
    except TokenizerContractError:return failure('TOKENIZER_CONTRACT',500)
    except Exception:return failure('MODEL_INFERENCE_ERROR',500)


if __name__=='__main__':
    import argparse
    import torch
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,default=HERE);parser.add_argument('--seed',type=int,choices=[42,43,44],default=42)
    parser.add_argument('--manifest-sha',required=True)
    args=parser.parse_args();torch.set_num_threads(2)
    predictor=ResearchPredictor(args.bundle,args.seed,expected_manifest_sha=args.manifest_sha)
    for line in sys.stdin:
        try:request=json.loads(line)
        except json.JSONDecodeError:
            print(json.dumps(dict(ok=False,status='error',http_status=400,result=None,error=dict(code='INVALID_JSON'))),flush=True);continue
        print(json.dumps(serve_request(predictor,request),ensure_ascii=False),flush=True)
