"""One-time custodian creation of a DPAPI/ACL sealed synthetic TEST vault.

No decrypt/evaluate entry point is provided. The roundtrip is checked only during
creation, before source deletion and ACL isolation. Development identities cannot seal.
"""
from __future__ import annotations

import argparse
import csv
import ctypes
from ctypes import wintypes
import hashlib
import json
from pathlib import Path
import subprocess

from stage3_data import (ROOT, BASE, AUTHORED, REPORT, LABELS, MODEL, V1_TEXT, AUX,
                        parse_batch, validate, stats, texts, compare, jsonl, all_public)
from expanded_common import require, sha, write_json, publish

VAULT = ROOT.parents[1]/'.sealed/koelectra-v2-stage3-20261109-v1'


class Blob(ctypes.Structure):
    _fields_ = [('size', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_ubyte))]


def dpapi(payload, *, check=False):
    memory = ctypes.create_string_buffer(payload)
    source = Blob(len(payload), ctypes.cast(memory, ctypes.POINTER(ctypes.c_ubyte)))
    target = Blob()
    dll = ctypes.WinDLL('crypt32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    fn = dll.CryptUnprotectData if check else dll.CryptProtectData
    fn.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                   ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    fn.restype = wintypes.BOOL
    ok = fn(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target))
    require(ok, f'DPAPI failed: {ctypes.get_last_error()}')
    try:
        return ctypes.string_at(target.data, target.size)
    finally:
        kernel.LocalFree.argtypes = [ctypes.c_void_p]
        kernel.LocalFree(ctypes.cast(target.data, ctypes.c_void_p))


def batch_check(path):
    records = parse_batch(path)
    summary = validate(records, expected=8)
    require(all(c['split'] == 'test' for c in records), 'TEST only')
    earlier = [p for p in sorted(AUTHORED.glob('test_*.txt')) if p.name < path.name]
    prior = all_public() + [c for p in earlier for c in parse_batch(p)]
    report = dict(status='PASS_STRUCTURE_NOT_HUMAN_REVIEWED', source_sha256=sha(path), stats=summary,
                  against_earlier=compare(texts(records), texts(prior)),
                  within_batch=compare(texts(records), texts(records), within=True),
                  body_retention='temporary_until_custodian_seal')
    write_json(REPORT/'batches'/f'{path.stem}.json', report)
    print(path.stem, len(records), 'PASS', report['against_earlier']['candidate_count'], flush=True)


def seal():
    identity = subprocess.check_output(['whoami'], text=True, errors='replace').strip()
    require('codexsandbox' not in identity.lower(), 'Custodian user context is required; development identity cannot seal')
    sid_text = subprocess.check_output(['whoami','/user','/fo','csv','/nh'], text=True, errors='replace')
    sid = list(csv.reader(sid_text.strip().splitlines()))[0][1]
    require(sid.startswith('S-1-5-'), 'Unexpected custodian SID')
    sources = [AUTHORED/f'test_{i:02d}.txt' for i in range(1,6)]
    require(all(p.is_file() for p in sources), 'Five actual authored batches required')
    require(not VAULT.exists(), 'Never overwrite an existing vault')
    records = [c for p in sources for c in parse_batch(p)]
    validate(records, expected=40)
    public = all_public()
    require(not {c['scenario_family_id'] for c in records} & {c['scenario_family_id'] for c in public}, 'Cross-role family overlap')
    duplicates = dict(test_internal=compare(texts(records), texts(records), within=True),
        test_vs_public=compare(texts(records), texts(public)),
        test_vs_v1=compare(texts(records), [(f"{r['conversation_id']}:{r['utterance_id']}", __import__('stage3_data').normalize(r['tuned_text'])) for r in jsonl(V1_TEXT)]),
        test_vs_aux=compare(texts(records), texts([dict(c, conversation_id=c['synthetic_id']) for c in jsonl(AUX)])))
    # Structural CPU check before sealing; no model, predictions, optimizer or threshold computation.
    from expanded_assets import load_tokenizer
    from risk_speech_ai.dataset import RiskSpeechDataset, make_training_dataloader
    from risk_speech_ai.training_data import TrainingSample
    from risk_speech_ai.labels import to_multi_hot
    import torch
    tok = load_tokenizer()
    samples = [TrainingSample(c['conversation_id'], u['utterance_id'],
                [x['text'] for x in c['utterances'][max(0,i-5):i]], u['text'], float(u['is_phishing']), to_multi_hot(u['labels']))
               for c in records for i,u in enumerate(c['utterances'])]
    loader = make_training_dataloader(RiskSpeechDataset(samples, tokenizer=tok), tokenizer=tok, batch_size=8, shuffle=False)
    count = batches = 0
    for batch in loader:
        n,width = batch['input_ids'].shape
        require(width <= 512 and batch['risk_target'].shape == (n,1) and batch['type_targets'].shape == (n,8), 'TEST structure tensor mismatch')
        require(all(t.device.type == 'cpu' for t in batch.values()), 'CPU required')
        require(batch['risk_target'].dtype == batch['type_targets'].dtype == torch.float32, 'TEST target dtype mismatch')
        count += n; batches += 1
    require(count == 320, 'Unexpected TEST sample count')
    body = dict(schema='sealed-internal-test-payload/1', purpose='internal_experiment', model=MODEL,
                conversations=records, authoring_sources=[dict(name=p.name, sha256=sha(p), text=p.read_text(encoding='utf-8')) for p in sources],
                semantic_independence='NOT_HUMAN_VERIFIED', human_approved=False)
    plaintext = json.dumps(body, ensure_ascii=False, separators=(',',':')).encode()
    plain_sha = hashlib.sha256(plaintext).hexdigest()
    encrypted = dpapi(plaintext)
    require(hashlib.sha256(dpapi(encrypted, check=True)).hexdigest() == plain_sha, 'DPAPI roundtrip mismatch')
    VAULT.mkdir(parents=True, exist_ok=False)
    blob_path = VAULT/'test40.dpapi'
    publish(blob_path, lambda stream: stream.write(encrypted))
    publish(VAULT/'.gitignore', lambda stream: stream.write(b'*\n'))
    cipher_sha = sha(blob_path)
    # Remove only these five newly-created authoring files, after verified ciphertext exists.
    for p in sources:
        require(p.resolve().is_relative_to(AUTHORED.resolve()) and p.name in {f'test_{i:02d}.txt' for i in range(1,6)}, 'Unsafe source cleanup')
        p.unlink()
    acl = subprocess.run(['icacls', str(VAULT), '/inheritance:r', '/grant:r',
                          f'*{sid}:(OI)(CI)F', '*S-1-5-18:(OI)(CI)F'], capture_output=True, text=True, errors='replace')
    require(acl.returncode == 0, 'Vault ACL isolation failed')
    child_acl = subprocess.run(['icacls', str(blob_path), '/reset'], capture_output=True, text=True, errors='replace')
    require(child_acl.returncode == 0, 'Ciphertext ACL inheritance reset failed')
    acl_text = subprocess.check_output(['icacls', str(VAULT)], text=True, errors='replace')
    receipt = dict(schema='stage3-sealed-test-receipt/1', sealed=True, encryption='Windows DPAPI user scope',
        vault_path=str(blob_path), ciphertext_sha256=cipher_sha, payload_sha256=plain_sha,
        custodian_sid=sid, custodian_windows_identity=identity, acl_inheritance_removed=True,
        allowed_principals=[sid,'S-1-5-18'], phase5_release_required=True,
        human_label_review_complete=False, deployment_approved=False, purpose='internal_experiment',
        stats=stats(records), source_batches=[dict(name=p.name, sha256=item['sha256']) for p,item in zip(sources, body['authoring_sources'])],
        split_membership=[dict(conversation_id=c['conversation_id'], scenario_family_id=c['scenario_family_id'], role='test') for c in records],
        duplicate_checks=duplicates, structure_cpu=dict(samples=count,batches=batches,model_forward=False,optimizer_updates=0),
        plaintext_authoring_removed=True, acl_audit=acl_text,
        note='Windows user sealing is access control, not a human label/use approval')
    write_json(BASE/'test_seal_receipt.json', receipt)
    print('SEALED', len(records), count, cipher_sha, flush=True)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['batch','seal'])
    parser.add_argument('--source',type=Path)
    args=parser.parse_args()
    batch_check(args.source) if args.mode == 'batch' else seal()
