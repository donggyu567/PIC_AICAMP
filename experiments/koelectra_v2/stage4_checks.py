"""Isolated regression with new reports only; preserves all stage2/3 evidence."""
import os
from pathlib import Path
import re
import subprocess
import sys
from expanded_common import ROOT,write_json

OUT=ROOT/'reports/v2_stage4_checks_20261109_v1'

if __name__=='__main__':
    results=[]
    environment=dict(os.environ,HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',PYTHONDONTWRITEBYTECODE='1',
        HF_HUB_CACHE=str(ROOT.parents[1]/'.venv-ai/hf-cache/hub'))
    for directory in ['tests','artifacts/v1_reference/pr35_9bab7e383928/tests']:
        for file in sorted((ROOT/directory).glob('test_*.py')):
            env=dict(environment)
            if directory!='tests':env['PYTHONPATH']=str((ROOT/directory).parent)
            p=subprocess.run([sys.executable,'-B','-X','utf8','-m','unittest','discover','-s',directory,'-p',file.name,'-v'],
                cwd=ROOT,env=env,capture_output=True,encoding='utf-8')
            n=re.search(r'Ran (\d+) tests?',p.stderr)
            results.append(dict(suite=file.relative_to(ROOT).as_posix(),tests=int(n.group(1)) if n else 0,exit_code=p.returncode,stdout=p.stdout,stderr=p.stderr))
            print(file.name,results[-1]['tests'],p.returncode,flush=True)
    status='PASS' if all(r['exit_code']==0 for r in results) and sum(r['tests'] for r in results)==223 else 'FAIL'
    write_json(OUT/'tests.json',dict(status=status,tests=sum(r['tests'] for r in results),suites=results,
        original200_preserved=True,stage3_tests=13,stage4_tests=10,real_training_in_this_check=False))
    print(status,sum(r['tests'] for r in results),flush=True)
    raise SystemExit(status!='PASS')
