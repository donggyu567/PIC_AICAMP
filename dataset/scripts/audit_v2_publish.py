#!/usr/bin/env python3
"""Select and inspect publication files; never stage or publish automatically.

The generated NUL list is an explicit path list for a separate authorized Git
operation. Raw source snapshots and connector payloads are local-only.
"""
import csv
import hashlib
import json
import re
import subprocess
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'reports/v2_publish'
ROOTS=('artifacts/v1_recovered_8faa6a7eebfe/','artifacts/v2_experiment_assets/',
       'dataset/04. processed/v2_validation/','dataset/04. processed/v2_train_expansion/',
       'dataset/review/v2_validation/','dataset/review/v2_train_expansion/',
       'experiments/koelectra_v2/','reports/v2_validation/','reports/v2_train_expansion/',
       'reports/v2_pipeline_audit/','reports/v2_experiment_design/','reports/v2_publish/')
CODE={'dataset/scripts/'+n for n in ('audit_v2_pipeline.py','audit_v2_publish.py','generate_v2_validation.py',
      'prepare_v2_train_expansion.py','recover_v1_inputs_audit.py','search_v1_assets_audit.py','v2_pipeline_gate.py',
      'validate_v2_train_expansion.py','validate_v2_validation.py','write_v2_pipeline_review_queue.py')}
CODE|={'tests/'+n for n in ('test_koelectra_experiment_design.py','test_v2_pipeline_gate.py','test_v2_train_expansion.py','test_v2_validation.py')}
PII={
    'phone':re.compile(r'(?<!\d)01[016789][ -]?\d{3,4}[ -]?\d{4}(?!\d)'),
    'rrn':re.compile(r'(?<!\d)\d{6}[ -]?[1-4]\d{6}(?!\d)'),
    'email':re.compile(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}'),
    'account_like':re.compile(r'(?<!\w)\d{3,6}[- ]\d{2,6}[- ]\d{3,8}(?!\w)')}
SECRETS={
    'private_key':re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    'github_token':re.compile(r'\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})\b'),
    'openai_token':re.compile(r'\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{30,}\b'),
    'aws_access_key':re.compile(r'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b'),
    'google_api_key':re.compile(r'\bAIza[0-9A-Za-z_-]{30,}\b')}


def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT).decode('utf-8')
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def jsonl(path):return [json.loads(s) for s in path.read_text(encoding='utf-8-sig').splitlines()]
def strings(value,path=''):
    if isinstance(value,str):yield path,value
    elif isinstance(value,dict):
        for k,v in value.items():yield from strings(v,path+'/'+k)
    elif isinstance(value,list):
        for i,v in enumerate(value):yield from strings(v,f'{path}/{i}')


def inspect_files(paths):
    issues=[];technical_hash_matches=0;total=0
    for name in paths:
        p=ROOT/name;data=p.read_bytes();total+=len(data)
        if len(data)>5*1024*1024 or p.suffix.lower() in ('.pt','.pth','.bin','.safetensors','.onnx','.pyc','.dll','.zip','.nul'):
            issues.append(dict(path=name,kind='binary_or_large_file'));continue
        try:text=data.decode('utf-8-sig')
        except UnicodeDecodeError:
            try:text=data.decode('utf-16')
            except UnicodeDecodeError:issues.append(dict(path=name,kind='unsupported_binary'));continue
        for kind,pattern in SECRETS.items():
            if pattern.search(text):issues.append(dict(path=name,kind=kind))
        records=[]
        if p.suffix=='.jsonl':
            for i,line in enumerate(text.splitlines(),1):records.extend((f'line:{i}{loc}',s) for loc,s in strings(json.loads(line)))
        elif p.suffix=='.json':records=list(strings(json.loads(text)))
        elif p.suffix=='.csv':records=[(f'row:{i}/{k}',v) for i,row in enumerate(csv.DictReader(text.splitlines()),2) for k,v in row.items() if v]
        else:records=[('file',text)]
        for location,value in records:
            if location.endswith('/raw_text'):
                issues.append(dict(path=name,location=location,kind='raw_text_field_not_for_publication'))
            # SHA/Git blob strings are identifiers of artifacts, not phone/RRN.
            sanitized=re.sub(r'(?i)\b[0-9a-f]{40,128}\b','[ARTIFACT_HASH]',value)
            technical_hash_matches+=int(sanitized!=value)
            for kind,pattern in PII.items():
                for match in pattern.finditer(sanitized):
                    token=match.group()
                    if kind=='email' and token.rsplit('@',1)[-1] in {'example.com','example.invalid'}:continue
                    if kind=='account_like' and set(re.sub(r'\D','',token))<={'0'}:continue
                    issues.append(dict(path=name,location=location,kind=kind))
    return dict(files=len(paths),total_bytes=total,issues=issues,technical_hash_fields_recognized=technical_hash_matches,
                limitation='Pattern screen plus transcript/source review; no claim that regex proves absence of all possible personal data.')


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    untracked=[p for p in git('ls-files','--others','--exclude-standard','-z').split('\0') if p]
    selected=[p for p in untracked if p in CODE or p.startswith(ROOTS)]
    changed=[p for p in git('diff','--name-only','-z').split('\0') if p]
    if set(changed)-{'.gitignore','.gitattributes'}:raise ValueError('Unexpected tracked source/data changes')
    selected=sorted(set(selected+changed))
    excluded=[p for p in untracked if p not in selected]
    report=inspect_files(selected)
    assert not report['issues'],json.dumps(report['issues'],ensure_ascii=False)
    train=jsonl(ROOT/'dataset/04. processed/v2_train_expansion/train_24_mixed_review_candidate.jsonl')
    val=jsonl(ROOT/'dataset/04. processed/v2_validation/validation_24_generated.jsonl')
    assert len(train)==len(val)==24 and sum(len(c['utterances']) for c in train)==208 and sum(len(c['utterances']) for c in val)==192
    assert all(c['split']=='train' and c['review_status']=='generated' for c in train)
    assert all(c['split']=='validation' and c['review_status']=='generated' for c in val)
    assert all('review_preparation' not in c for c in train[16:]+val)
    for rel,count in [('dataset/review/v2_train_expansion/human_review_new8.csv',72),('dataset/review/v2_validation/human_review.csv',192)]:
        with (ROOT/rel).open(encoding='utf-8-sig',newline='') as f:reviews=list(csv.DictReader(f))
        assert len(reviews)==count and all(r['검수_결과_김해린']==r['검수_결과_임정윤']==r['최종_합의_결과']=='미승인' for r in reviews)
    baseline=json.loads((ROOT/'reports/v2_experiment_design/protected_baseline.json').read_text(encoding='utf-8'))
    modified=[p for p,s in baseline['files'].items() if not (ROOT/p).is_file() or digest(ROOT/p)!=s]
    assert not modified,modified
    assert digest(ROOT/'artifacts/v1_recovered_8faa6a7eebfe/prepared/labels.jsonl')=='c205049e1aa2125ad40cc6cea1465b2c2793cc7fedf02b7eab8e1d9f20e9c9e5'
    assert digest(ROOT/'artifacts/v1_recovered_8faa6a7eebfe/prepared/tuned.jsonl')=='50ea88cc3ee9c3df1477082ab5daf82ef77f83329374b50f312874592462e6f2'
    report.update(status='PASS_SELECTED_PUBLICATION_FILES',branch=git('branch','--show-current').strip(),base_commit=git('rev-parse','HEAD').strip(),
        selected_files=selected,untracked_excluded=excluded,protected_files_unchanged=len(baseline['files']),
        exclusions=dict(raw_source_snapshot='all70 source_snapshot files: unmasked identifiers/raw_text retained locally',
            raw_source_payload='recovered_source_payloads.json contains unmasked identifiers',
            remote_debug_captures='audit_*.json and drive_checkpoint_search*.json not needed for public source distribution',
            private_research='phishing_candidate_research_jeongyun_202609w4.md excluded by explicit instruction',
            weights_and_environments='ignored model/venv/cache assets; only asset metadata and scoped ignore file included'),
        human_review_promoted=False,actual_training_executed=False,
        file_sha256={p:digest(ROOT/p) for p in selected if p!='reports/v2_publish/publication_audit.json'})
    (OUT/'publication_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    # Regenerate after the report exists so it is included in the explicit list.
    selected=sorted(set(selected+['reports/v2_publish/publication_audit.json']))
    (OUT/'stage_paths.nul').write_bytes(b'\0'.join(p.encode('utf-8') for p in selected)+b'\0')
    print(json.dumps({k:report[k] for k in ('status','files','total_bytes','issues','protected_files_unchanged')},indent=2))
    print('explicit_stage_files',len(selected))


if __name__=='__main__':main()
