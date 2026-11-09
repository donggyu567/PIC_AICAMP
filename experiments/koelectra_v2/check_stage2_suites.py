"""Process-isolated complete regression, including controlled fixture-only updates."""
from pathlib import Path
import os
import re
import subprocess
import sys

from expanded_common import ROOT, write_json, read, sha

OUT = ROOT/'reports/v2_stage2_20261109'


if __name__ == '__main__':
    recheck_expanded = '--recheck-expanded' in sys.argv
    previous = read(OUT/'tests.json') if recheck_expanded else None
    changed = {'test_expanded_pipeline.py', 'test_expanded_guards.py'}
    results = [r for r in previous['suites'] if Path(r['suite']).name not in changed] if previous else []
    environment = dict(os.environ, HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
                       HF_HUB_CACHE=str(ROOT.parents[1]/'.venv-ai/hf-cache/hub'), PYTHONDONTWRITEBYTECODE='1')
    for directory in ['tests', 'artifacts/v1_reference/pr35_9bab7e383928/tests']:
        for file in sorted((ROOT/directory).glob('test_*.py')):
            if recheck_expanded and file.name not in changed:
                continue
            env = dict(environment)
            if directory != 'tests':
                env['PYTHONPATH'] = str((ROOT/directory).parent)
            process = subprocess.run([sys.executable, '-B', '-X', 'utf8', '-m', 'unittest', 'discover',
                                      '-s', directory, '-p', file.name, '-v'], cwd=ROOT, env=env,
                                     capture_output=True, encoding='utf-8')
            count = re.search(r'Ran (\d+) tests?', process.stderr)
            result = dict(suite=file.relative_to(ROOT).as_posix(), exit_code=process.returncode,
                          tests=int(count.group(1)) if count else 0, stdout=process.stdout, stderr=process.stderr)
            results.append(result)
            print(file.name, result['tests'], process.returncode, flush=True)
    report = dict(status='PASS' if all(r['exit_code'] == 0 for r in results) else 'FAIL',
                  tests=sum(r['tests'] for r in results), suites=results,
                  real_dataset_training=False, real_validation_selection=False, test_inference=False,
                  temporary_fixture_updates_only=True)
    if previous:
        report['unchanged_suite_source'] = dict(path='tests.json', sha256=sha(OUT/'tests.json'))
    destination = OUT/'tests.json'
    if destination.exists():
        index = 2
        while (OUT/f'tests_attempt_{index}.json').exists():
            index += 1
        destination = OUT/f'tests_attempt_{index}.json'
    write_json(destination, report)
    print(destination, report['status'], report['tests'], flush=True)
    raise SystemExit(report['status'] != 'PASS')
