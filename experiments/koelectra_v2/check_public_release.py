"""Public-checkout regression, without private corpora, TEST IO or real training."""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
REFERENCE=ROOT/'artifacts/v1_reference/pr35_9bab7e383928'

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():raise FileExistsError('Choose a new report path; existing evidence is preserved')
    suites=[]
    names=['test_expanded_guards.py','test_expanded_pipeline.py','test_stage3_data.py','test_stage4_exploratory.py','test_stage5_handoff.py']
    paths=[ROOT/'tests'/name for name in names]+sorted((REFERENCE/'tests').glob('test_*.py'))
    for p in paths:
        env=dict(os.environ,HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=str(REFERENCE))
        result=subprocess.run([sys.executable,'-B','-X','utf8','-m','unittest','discover','-s',str(p.parent),'-p',p.name,'-v'],cwd=ROOT,env=env,capture_output=True,text=True,encoding='utf-8')
        count=re.search(r'Ran (\d+) tests?',result.stderr);skip=re.search(r'OK \(skipped=(\d+)\)',result.stderr)
        # Public result retains relative suite names and counts, not user/environment paths.
        suites.append(dict(suite=p.relative_to(ROOT).as_posix(),tests=int(count[1]) if count else 0,skipped=int(skip[1]) if skip else 0,exit_code=result.returncode))
        if result.returncode:print(result.stderr,flush=True)
        print(p.name,suites[-1],flush=True)
    report=dict(status='PASS' if all(s['exit_code']==0 for s in suites) else 'FAIL',run_at=datetime.now(timezone.utc).isoformat(),tests=sum(s['tests'] for s in suites),skipped=sum(s['skipped'] for s in suites),suites=suites,scope='Selected public AI suites; not full repository tests',real_model_training=False,optimizer_updates='Temporary tiny unit fixtures only',test_body_access=False,skip_reason='Private TRAIN/VALIDATION/manifest-dependent checks intentionally unavailable in public checkout')
    report['passed']=report['tests']-report['skipped'] if report['status']=='PASS' else None
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8') as stream:json.dump(report,stream,ensure_ascii=False,indent=2)
    print('PUBLIC REGRESSION',report['status'],report['tests'],report['skipped'],flush=True)
    return report['status']!='PASS'

if __name__=='__main__':raise SystemExit(main())
