"""Run original regression suites in isolated processes without changing stage-2 reports."""
import os
from pathlib import Path
import re
import subprocess
import sys
from expanded_common import ROOT, write_json
from stage3_data import REPORT


if __name__ == '__main__':
    results = []
    environment = dict(os.environ, HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
        HF_HUB_CACHE=str(ROOT.parents[1]/'.venv-ai/hf-cache/hub'), PYTHONDONTWRITEBYTECODE='1')
    for directory in ['tests', 'artifacts/v1_reference/pr35_9bab7e383928/tests']:
        for file in sorted((ROOT/directory).glob('test_*.py')):
            env = dict(environment)
            if directory != 'tests':
                env['PYTHONPATH'] = str((ROOT/directory).parent)
            result = subprocess.run([sys.executable, '-B', '-X', 'utf8', '-m', 'unittest', 'discover',
                '-s', directory, '-p', file.name, '-v'], cwd=ROOT, env=env, capture_output=True, encoding='utf-8')
            match = re.search(r'Ran (\d+) tests?', result.stderr)
            results.append(dict(suite=file.relative_to(ROOT).as_posix(), exit_code=result.returncode,
                tests=int(match.group(1)) if match else 0, stdout=result.stdout, stderr=result.stderr))
            print(file.name, results[-1]['tests'], result.returncode, flush=True)
    old = [r for r in results if Path(r['suite']).name != 'test_stage3_data.py']
    report = dict(status='PASS' if all(r['exit_code'] == 0 for r in results) and sum(r['tests'] for r in old) == 200 else 'FAIL',
        tests=sum(r['tests'] for r in results), original_regression_tests=sum(r['tests'] for r in old), suites=results,
        real_dataset_training=False, real_validation_selection=False, test_inference=False,
        note='Existing optimizer tests use temporary tiny fixtures only; no corpus or real model training')
    write_json(REPORT/'tests.json', report)
    print(report['status'], report['tests'], flush=True)
    raise SystemExit(report['status'] != 'PASS')
