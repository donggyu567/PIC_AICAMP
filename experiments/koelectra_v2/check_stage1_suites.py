"""Run each historical suite in a fresh process to isolate pinned import paths."""
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'reports/v2_stage1_20261109'

if __name__ == '__main__':
    retry = '--retry-failed' in sys.argv
    previous = json.loads((OUT / 'tests.json').read_text(encoding='utf-8')) if retry else []
    if retry:
        (OUT / 'tests_initial_import_path.json').write_text(json.dumps(previous, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    suites = [s for s in previous if s['exit_code'] == 0]
    passed = {s['suite'] for s in suites}
    env = dict(os.environ, HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', PYTHONDONTWRITEBYTECODE='1')
    for directory in ['tests', 'artifacts/v1_reference/pr35_9bab7e383928/tests']:
        for file in sorted((ROOT / directory).glob('test_*.py')):
            if file.relative_to(ROOT).as_posix() in passed:
                continue
            suite_env = dict(env)
            if directory != 'tests':
                suite_env['PYTHONPATH'] = str((ROOT / directory).parent)
            proc = subprocess.run([sys.executable, '-B', '-X', 'utf8', '-m', 'unittest', 'discover', '-s', directory, '-p', file.name, '-v'],
                                  cwd=ROOT, env=suite_env, capture_output=True, encoding='utf-8')
            suites.append(dict(suite=file.relative_to(ROOT).as_posix(), exit_code=proc.returncode,
                               stdout=proc.stdout, stderr=proc.stderr))
            print(file.name, proc.returncode, flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'tests.json').write_text(json.dumps(suites, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    raise SystemExit(any(s['exit_code'] for s in suites))
