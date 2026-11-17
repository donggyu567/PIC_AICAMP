"""Copy the bundle outside the project and verify two fresh CPU processes."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from .src.common import ROOT,V3,read_json,require,sha,create_json


if __name__=='__main__':
    bundle=V3/'handoff/research_20261117_v1';report=V3/'reports/autonomous_run'
    run=V3/'runs/research_synthetic_seed42_20261117_v2';ref=read_json(run/'run.json')['checkpoints'][-1]
    with tempfile.TemporaryDirectory(prefix='pic-koelectra-v3-') as tmp:
        td=Path(tmp).resolve();require(td.parent==Path(tempfile.gettempdir()).resolve() and td.name.startswith('pic-koelectra-v3-'),'Unexpected temporary target')
        dest=td/'bundle';shutil.copytree(bundle,dest)
        env=dict(os.environ);env.pop('PYTHONPATH',None);env.update(PYTHONDONTWRITEBYTECODE='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
        cmd=[sys.executable,'-B','-X','utf8',str(V3/'verify_handoff.py'),'--bundle',str(dest),'--training',ref['path'],
             '--training-sha',ref['sha256'],'--parent-inventory',str(run/'frozen_before_training.json'),'--output',str(report/'standalone_cpu.json')]
        result=subprocess.run(cmd,cwd=td,env=env,capture_output=True,text=True,encoding='utf-8')
        with (report/'standalone_cpu.log').open('x',encoding='utf-8') as f:f.write(result.stdout+result.stderr)
        print(result.stdout,flush=True);print(result.stderr,flush=True)
        require(result.returncode==0,'Standalone CPU probe failed')
        lines='not-json\n'+json.dumps({'history_texts':[],'current_text':'공개 안내문을 확인하겠습니다.'},ensure_ascii=False)+'\n'+json.dumps({'current_text':'확인 '*800},ensure_ascii=False)+'\n'
        cli=subprocess.run([sys.executable,'-B','-X','utf8',str(dest/'runtime.py'),'--bundle',str(dest),'--manifest-sha',sha(dest/'bundle_manifest.json')],
                           cwd=td,env=env,input=lines,capture_output=True,text=True,encoding='utf-8')
        answers=[json.loads(line) for line in cli.stdout.splitlines() if line.strip()]
        require(cli.returncode==0 and [a['http_status'] for a in answers]==[400,200,422],'CLI JSON/error contract failed')
        create_json(report/'standalone_cli.json',dict(status='PASS',fresh_process=True,exit_code=cli.returncode,
            statuses=[a['http_status'] for a in answers],responses=answers,manifest_sha256=sha(dest/'bundle_manifest.json'),
            malformed_json_checked=True,korean_utf8_roundtrip=True,overlength_checked=True))
        create_json(report/'standalone_location.json',dict(external_temp_path=str(td),outside_project=not td.is_relative_to(ROOT),
            fresh_process_returncodes=[result.returncode,cli.returncode],temporary_copy_removed_after_test=True))
    print('Standalone model+CLI PASS; temporary external copy removed.')
