"""Pinned PR35 imports and shared, fail-closed runtime primitives."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
REFERENCE = ROOT / 'artifacts/v1_reference/pr35_9bab7e383928'
sys.path.insert(0, str(REFERENCE))
from risk_speech_ai import labels as pinned_labels
if not Path(pinned_labels.__file__).resolve().is_relative_to(REFERENCE.resolve()):
    raise ImportError('Run expanded modules in a fresh process with the pinned PR35 package')
from risk_speech_ai.labels import LABELS

MODEL = 'monologg/koelectra-base-v3-discriminator'
REVISION = '68b30cd259f34a4b5aa8786392612ba2a2617fcc'
PROTOCOL = ROOT / 'experiments/koelectra_v2/protocol_20261109_v1.json'
PROTOCOL_SHA = 'a98c283b0b133fb35473bf1e9b1f8fc3516472fc1c3ac606b2fe888dfae35497'
OUTPUT = ROOT / 'artifacts/v2_comparison_runs/expansion_20261109_v1'
SEEDS = (42, 43, 44)
ARMS = ('A0', 'A_epoch', 'B_ratio', 'B_threshold', 'C_approved', 'B_step_matched', 'B_sqrt5_legacy')


class GateError(ValueError):
    """Required authorization, provenance or numerical contract is missing."""


def require(condition, message):
    if not condition:
        raise GateError(message)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def sha(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def read(path):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, f'Duplicate JSON key: {key}')
            result[key] = value
        return result
    return json.loads(Path(path).read_text(encoding='utf-8-sig'), object_pairs_hook=pairs,
                      parse_constant=lambda x: (_ for _ in ()).throw(GateError(f'Non-finite JSON: {x}')))


def checked_file(root, spec):
    require(isinstance(spec, dict) and set(spec) == {'path', 'sha256'}, 'Expected path/sha256 reference')
    name = spec['path']
    require(isinstance(name, str) and not Path(name).is_absolute() and ':' not in name and '\\' not in name,
            'References must be portable relative paths')
    root = Path(root).resolve()
    path = (root / name).resolve()
    require(path.is_relative_to(root) and path.is_file(), f'Missing or escaping reference: {name}')
    require(re.fullmatch('[0-9a-f]{64}', spec['sha256']) and sha(path) == spec['sha256'], f'Hash mismatch: {name}')
    return path


def slug(value):
    require(isinstance(value, str) and re.fullmatch('[A-Za-z0-9_-]{1,80}', value), 'Unsafe run identifier')
    return value


def publish(path, write):
    """Flush a temporary inode then link atomically without replacing any target."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.pending-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            write(stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(name, path)  # atomic create-if-absent on Windows and POSIX
    finally:
        Path(name).unlink(missing_ok=True)
    return path


def write_json(path, value):
    payload = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()
    return publish(path, lambda stream: stream.write(payload))


def load_design(path=PROTOCOL):
    require(sha(path) == PROTOCOL_SHA, 'Design changed: register a new compiler/protocol version')
    design = read(path)
    require(design['input']['label_order'] == list(LABELS), 'Canonical label order changed')
    return design


def compile_runtime(arm, seed, *, frozen=None):
    """Convert the immutable design into a separate runtime schema; no permissions implied."""
    load_design()
    require(arm in ARMS and seed in SEEDS and type(seed) is int, 'Unknown arm/seed')
    require(arm != 'B_threshold', 'B_threshold is selection of B checkpoints, not another training run')
    config = dict(schema='expanded-runtime/1', protocol_sha256=PROTOCOL_SHA,
                  arm=arm, seed=seed, model_revision=REVISION, tokenizer_revision=REVISION,
                  epochs=1 if arm == 'A0' else 3, batch_size=8, learning_rate=2e-5,
                  weight_decay=.01, initialization='fresh_pinned_public_encoder_and_seeded_heads',
                  weight_policy='none' if arm in ('A0', 'A_epoch') else
                  ('sqrt5' if arm == 'B_sqrt5_legacy' else 'ratio10'), thresholds=[.5] * 9,
                  threshold_version='initial-0.5', max_steps=None)
    if arm in ('C_approved', 'B_step_matched'):
        require(frozen is not None, 'B selection bundle is required')
        from expanded_selection import validate_frozen
        validate_frozen(frozen)
        config.update(epochs=frozen['epoch'], frozen_weights=frozen['weights'],
                      thresholds=frozen['thresholds'], threshold_version=frozen['version'],
                      selection_sha256=digest(frozen), frozen_selection=frozen)
    return config


def validate_runtime(config):
    require(isinstance(config, dict) and config.get('schema') == 'expanded-runtime/1',
            'A design JSON is not an executable runtime config')
    expected = compile_runtime(config['arm'], config['seed'], frozen=config.get('frozen_selection'))
    # Derived C step budget is bound to the approved data in the trainer, never a CLI override.
    require(config == expected, 'Runtime hyperparameters differ from the registered compiler')
    return config
