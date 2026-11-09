"""Run complete regression in isolated processes; never updates old test reports."""
import os
from pathlib import Path
import re
import subprocess
import sys
from expanded_common import ROOT,write_json
from stage5_prepare import REPORT

if __name__=='__main__':
    environment=dict(os.environ,HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',PYTHONDONTWRITEBYTECODE='1',
        HF_HUB_CACHE=str(ROOT.parents[1]/'.venv-ai/hf-cache/hub'))
    results=[]
    for directory in ['tests','artifacts/v1_reference/pr35_9bab7e383928/tests']:
        for file in sorted((ROOT/directory).glob('test_*.py')):
            env=dict(environment)
            if directory!='tests':env['PYTHONPATH']=str((ROOT/directory).parent)
            p=subprocess.run([sys.executable,'-B','-X','utf8','-m','unittest','discover','-s',directory,'-p',file.name,'-v'],
                cwd=ROOT,env=env,capture_output=True,encoding='utf-8')
            match=re.search(r'Ran (\d+) tests?',p.stderr)
            result=dict(suite=file.relative_to(ROOT).as_posix(),tests=int(match.group(1)) if match else 0,
                exit_code=p.returncode,stdout=p.stdout,stderr=p.stderr)
            results.append(result);print(file.name,result['tests'],p.returncode,flush=True)
    new=[r for r in results if Path(r['suite']).name=='test_stage5_handoff.py']
    previous=sum(r['tests'] for r in results if Path(r['suite']).name!='test_stage5_handoff.py')
    ok=all(r['exit_code']==0 for r in results) and previous==223 and len(new)==1 and new[0]['tests']==17
    write_json(REPORT/'tests.json',dict(status='PASS' if ok else 'FAIL',tests=sum(r['tests'] for r in results),
        previous_regression_tests=previous,new_stage5_tests=new[0]['tests'] if new else 0,suites=results,
        test_body_access=False,real_model_training=False,note='Optimizer regression uses temporary tiny fixtures only; approval fixtures are in memory or temporary, never actual custodian releases'))
    print('PASS' if ok else 'FAIL',sum(r['tests'] for r in results),flush=True)
    raise SystemExit(not ok)
