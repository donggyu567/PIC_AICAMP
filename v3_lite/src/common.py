"""Pinned, read-only v2 dependencies and write boundaries."""
from __future__ import annotations

import hashlib
import importlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
V3 = ROOT / 'v3_lite'
V2 = Path(os.environ.get('PIC_V2_RESEARCH_ROOT', str(ROOT / '.worktrees/koelectra-v2-pilot-readiness'))).resolve()
BUNDLE = V2 / 'artifacts/v2_research_handoff/stage5_final_20261110_v1'
REFERENCE = V2 / 'artifacts/v1_reference/pr35_9bab7e383928'
RUNS = V3 / 'runs'
DATA = V3 / 'data'
LABELS = ('institution_impersonation', 'money_transfer', 'personal_information',
          'app_installation', 'secrecy', 'threat_pressure', 'loan_fraud', 'information_probing')
FOCUS = ('information_probing', 'personal_information')
REVISION = '68b30cd259f34a4b5aa8786392612ba2a2617fcc'
BUNDLE_SHA = 'fd452646aee020276888aea89f80667ac76b43234d634d1b600a744f9e99adc9'
PARENT_SHA = '0d14fadcc9dbd1a3ea3872074970d47f79148f76766d77188eb808b94ed9d2ee'


class GateError(ValueError):
    """Required evidence or invariant is absent."""


def require(condition, reason):
    if not condition:
        raise GateError(reason)


def sha(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(part)
    return value.hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def read_json(path):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, f'Duplicate JSON key: {key}')
            result[key] = value
        return result
    return json.loads(Path(path).read_text(encoding='utf-8-sig'), object_pairs_hook=pairs,
                      parse_constant=lambda x: (_ for _ in ()).throw(GateError(f'Nonfinite JSON: {x}')))


def inside(path, root):
    raw_root = Path(root).absolute()
    path, root = Path(path).resolve(), Path(root).resolve()
    if raw_root.is_relative_to(V3.absolute()):
        require(root.is_relative_to(V3.resolve()), 'v3 root redirects outside its workspace')
    require(path.is_relative_to(root) and path != root, f'Path outside required root: {root}')
    return path


def create_json(path, value, *, root=V3):
    path = inside(path, root)
    content = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        stream.write(content)


_ready = False


def bootstrap():
    """Verify the exact executed v2 source set before importing shared code."""
    global _ready
    if _ready:
        return
    sys.dont_write_bytecode = True
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['TRANSFORMERS_OFFLINE'] = '1'
    manifest = read_json(V2 / 'artifacts/v2_exploratory_runs/stage4_20261109_v1/execution_manifest.json')
    for name, expected in manifest['code'].items():
        require(sha(inside(V2 / name, V2)) == expected, f'Pinned source changed: {name}')
    require(sha(BUNDLE / 'bundle_manifest.json') == BUNDLE_SHA, 'Bundle manifest changed')
    for item in read_json(BUNDLE / 'bundle_manifest.json')['support_files']:
        require(sha(inside(BUNDLE / item['path'], BUNDLE)) == item['sha256'], 'Bundle support changed')
    if 'risk_speech_ai' in sys.modules:
        location = Path(sys.modules['risk_speech_ai'].__file__).resolve()
        require(location.is_relative_to(REFERENCE.resolve()), 'Wrong risk_speech_ai already imported; use a fresh process')
    for path in [V2 / 'experiments/koelectra_v2', REFERENCE]:
        sys.path.insert(0, str(path))
    labels = importlib.import_module('risk_speech_ai.labels')
    require(tuple(labels.LABELS) == LABELS, 'Canonical label order changed')
    require(Path(labels.__file__).resolve().is_relative_to(REFERENCE.resolve()), 'Wrong pinned core')
    _ready = True
