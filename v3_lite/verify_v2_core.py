"""Run only pinned data/tokenizer/metrics unit suites; never TEST/custody suites."""
import io
import json
import sys
import time
import unittest
from pathlib import Path
from .src.common import REFERENCE,V3,bootstrap,create_json


if __name__=='__main__':
    bootstrap()
    import torch
    torch.set_num_threads(1)
    stream=io.StringIO();start=time.monotonic()
    suite=unittest.defaultTestLoader.discover(str(REFERENCE/'tests'))
    result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    out=V3/'reports/autonomous_run'
    (out/'v2_core_regression.log').write_text(stream.getvalue(),encoding='utf-8')
    record=dict(status='PASS' if result.wasSuccessful() else 'FAIL',tests_run=result.testsRun,failures=len(result.failures),errors=len(result.errors),
                skipped=len(result.skipped),elapsed_seconds=time.monotonic()-start,scope='Pinned five core unit suites only: dataset,metrics,splits,tokenization,training_data',
                test_body_or_release_records_accessed=False,command=f'{sys.executable} -B -X utf8 -m v3_lite.verify_v2_core')
    create_json(out/'v2_core_regression.json',record)
    print(json.dumps(record,indent=2))
    raise SystemExit(0 if result.wasSuccessful() else 1)
