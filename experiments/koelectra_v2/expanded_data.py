"""External human evidence, role manifests and conversation-safe PR35 samples.

No manifest or approval is created here. Preflight can inspect candidates, but
only verified manifests can produce an authorized training/selection partition.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from collections import defaultdict
import json

from expanded_common import (ROOT, LABELS, REVISION, GateError, checked_file,
                             digest, read, require, sha)
from risk_speech_ai.training_data import TrainingSample
from risk_speech_ai.labels import to_multi_hot

REVIEWERS = {'김해린', '임정윤'}
ROLES = {'train', 'synthetic_train', 'validation', 'test'}


def decision(record, purpose):
    require(record.get('approved') is True and record.get('purpose') == purpose, f'Missing {purpose} approval')
    for key in ('by', 'at', 'evidence'):
        require(isinstance(record.get(key), str) and record[key].strip(), f'Missing human {key}')
    stamp = datetime.fromisoformat(record['at'])
    require(stamp.tzinfo is not None, 'Human decision timestamp must include timezone')


def validate_split(split):
    require(split.get('schema') == 'expanded-split/1' and split.get('frozen') is True, 'Split not frozen')
    members = split.get('conversations', {})
    require(bool(members), 'Empty split')
    groups = {key: {} for key in ('scenario_family_id', 'source_id', 'author_id')}
    for cid, item in members.items():
        require(isinstance(cid, str) and cid and item['role'] in ROLES, 'Invalid split membership')
        role = 'train' if item['role'] == 'synthetic_train' else item['role']
        for field, seen in groups.items():
            key = item[field]
            require(isinstance(key, str) and key.strip(), 'Missing source/family/author grouping')
            require(key not in seen or seen[key] == role, f'Cross-partition {field}: {key}')
            seen[key] = role
    return members


def row_key(row):
    return f"{row['conversation_id']}:{row['utterance_id']}"


@dataclass(frozen=True)
class Partition:
    root: Path
    manifest_path: Path
    manifest_sha256: str
    role: str
    rows: tuple
    bindings: dict
    authorized: bool
    fixture: bool

    def verify(self, allowed):
        require(self.authorized and self.role in allowed, 'Partition is not authorized for this operation')
        require(sha(self.manifest_path) == self.manifest_sha256, 'Manifest changed after validation')
        again = load_partition(self.root, self.manifest_path, self.role,
                               mode='final-evaluate' if self.role == 'test' else 'authorized',
                               fixture=self.fixture, test_capability=self.bindings.get('test_capability'))
        require(again.bindings == self.bindings and digest(again.rows) == digest(self.rows), 'Dataset/evidence changed')

    def samples(self):
        grouped = defaultdict(list)
        for row in self.rows:
            grouped[row['conversation_id']].append(row)
        samples = []
        for conversation in grouped.values():
            for index, row in enumerate(conversation):
                samples.append(TrainingSample(row['conversation_id'], row['utterance_id'],
                    [u['text'] for u in conversation[max(0, index-5):index]], row['text'],
                    float(row['is_phishing']), to_multi_hot(row['labels'])))
        return samples


def load_partition(root, manifest_path, role, *, mode='authorized', fixture=False, test_capability=None):
    root, path = Path(root).resolve(), Path(manifest_path).resolve()
    require(role in ROLES and mode in ('authorized', 'preflight', 'final-evaluate'), 'Unknown role/mode')
    require(path.is_relative_to(root) and path.is_file(), 'Required real manifest is absent')
    # Deny before opening the manifest or any dataset reference.
    if role == 'test':
        require(mode == 'final-evaluate' and test_capability is not None, 'TEST content is sealed')
        receipt = validate_test_capability(root, test_capability, path)
    manifest = read(path)
    require(manifest.get('schema') == 'expanded-data/1' and manifest.get('role') == role, 'Wrong manifest role/schema')
    require(manifest.get('fixture', False) is fixture, 'Fixture/production manifest mismatch')
    if fixture:
        require(not root.is_relative_to(ROOT) and root != ROOT, 'Fixture must be outside the project')
    require(manifest['label_order'] == list(LABELS) and manifest['model_revision'] == REVISION and
            manifest['tokenizer_revision'] == REVISION, 'Model/tokenizer/label revision mismatch')
    if role == 'test':
        require(manifest['data']['sha256'] == receipt['data_sha256'] and manifest['split']['sha256'] == receipt['split_sha256'],
                'TEST data/split differs from sealed receipt')
    require(isinstance(manifest.get('preprocessing_version'), str) and manifest['preprocessing_version'], 'Missing preprocessing version')
    split_path = checked_file(root, manifest['split'])
    members = validate_split(read(split_path))
    data_path = checked_file(root, manifest['data'])
    data = [json.loads(line) for line in data_path.read_text(encoding='utf-8').splitlines() if line.strip()]
    require(bool(data), 'Empty dataset (C requires actual approved synthetic rows)')
    keys, grouped = set(), defaultdict(list)
    for row in data:
        cid = row['conversation_id']
        require(cid in members and members[cid]['role'] == role, 'Role mixing / undeclared conversation')
        require(type(row['utterance_id']) is int and row['utterance_id'] > 0, 'Invalid utterance order')
        key = row_key(row)
        require(key not in keys, 'Duplicate utterance')
        keys.add(key)
        for field in ('scenario_family_id', 'source_id', 'author_id'):
            require(row[field] == members[cid][field], 'Grouping differs from frozen split')
        require(isinstance(row['text'], str) and row['text'].strip(), 'Missing masked text')
        require(type(row['is_phishing']) is bool and isinstance(row['labels'], list), 'Invalid labels')
        require(len(set(row['labels'])) == len(row['labels']) and set(row['labels']) <= set(LABELS), 'Unknown/duplicate labels')
        require(row['is_phishing'] or not row['labels'], 'Normal utterance has risk labels')
        require(not row['is_phishing'] or row['labels'] or row.get('out_of_taxonomy') is True, 'Unexplained empty risk labels')
        require(type(row.get('hard_negative')) is bool and (not row['hard_negative'] or not row['is_phishing']), 'Invalid hard-negative flag')
        require(row['origin'] in ('v1', 'new_synthetic', 'human', 'fixture'), 'Unknown provenance')
        require((role != 'train' or row['origin'] in ('v1', 'fixture')) and
                (role != 'synthetic_train' or row['origin'] in ('new_synthetic', 'human', 'fixture')), 'Wrong TRAIN provenance')
        if fixture:
            require(cid.startswith('FIXTURE_') and row['origin'] == 'fixture', 'Real data cannot use fixture path')
        else:
            require(row['origin'] != 'fixture', 'Fixture cannot enter production')
        grouped[cid].append(row)
    expected = {cid for cid, item in members.items() if item['role'] == role}
    require(set(grouped) == expected, 'Manifest must cover the complete registered partition')
    ordered = []
    for cid in sorted(grouped):
        conversation = sorted(grouped[cid], key=lambda u: u['utterance_id'])
        require([u['utterance_id'] for u in conversation] == list(range(1, len(conversation)+1)), 'Conversation has gaps')
        ordered.extend(conversation)
    bindings = dict(data_sha256=manifest['data']['sha256'], split_sha256=manifest['split']['sha256'],
                    preprocessing_version=manifest['preprocessing_version'], manifest_sha256=sha(path))
    authorized = mode != 'preflight'
    if authorized:
        approval_path = checked_file(root, manifest['approval'])
        approval = read(approval_path)
        require(approval.get('schema') == 'expanded-approval/1', 'Approval schema missing')
        for field in ('data_sha256', 'split_sha256', 'preprocessing_version'):
            require(approval[field] == bindings[field], f'Approval not bound to {field}')
        require(set(approval['scope_keys']) == keys and len(approval['scope_keys']) == len(keys), 'Approval coverage incomplete')
        purpose = 'training' if role in ('train', 'synthetic_train') else 'evaluation'
        require(set(approval['permissions']) == {r['source_id'] for r in data}, 'Rights coverage incomplete')
        for permission in approval['permissions'].values():
            decision(permission, purpose)
            require(isinstance(permission.get('rights_holder'), str) and permission['rights_holder'].strip(), 'Rights holder missing')
            checked_file(root, permission['evidence_file'])
        reviews = approval['reviews']
        require(len(reviews) == 2 and {r['by'] for r in reviews} == REVIEWERS, 'Two independent designated human reviewers required')
        for review in reviews:
            decision(review, 'review')
            require(set(review['scope_keys']) == keys and not review.get('unresolved'), 'Human review incomplete')
            checked_file(root, review['evidence_file'])
        for field, scope in [('final_agreement', 'final_agreement'), ('use_decision', purpose)]:
            decision(approval[field], scope)
            checked_file(root, approval[field]['evidence_file'])
        bindings['approval_sha256'] = sha(approval_path)
        if role == 'test':
            bindings['test_capability'] = test_capability
    return Partition(root, path, sha(path), role, tuple(ordered), bindings, authorized, fixture)


def check_disjoint(*partitions):
    require(len({p.bindings['split_sha256'] for p in partitions}) == 1, 'Different frozen splits')
    fields = ('conversation_id', 'scenario_family_id', 'source_id', 'author_id')
    for index, first in enumerate(partitions):
        for second in partitions[index+1:]:
            same_train = {first.role, second.role} <= {'train', 'synthetic_train'}
            for field in fields:
                if same_train and field != 'conversation_id':
                    continue
                require(not {r[field] for r in first.rows} & {r[field] for r in second.rows}, f'Cross-role leakage: {field}')


def validate_receipt(root, spec):
    path = checked_file(root, spec)
    receipt = read(path)
    require(receipt.get('schema') == 'sealed-test-receipt/1' and receipt.get('sealed') is True,
            'TEST sealing receipt absent')
    for field in ('data_sha256', 'manifest_sha256', 'split_sha256'):
        require(isinstance(receipt.get(field), str) and len(receipt[field]) == 64 and
                all(c in '0123456789abcdef' for c in receipt[field]), 'Invalid sealed hash')
    decision(receipt['custodian'], 'seal')
    require('rows' not in receipt and 'text' not in receipt and 'labels' not in receipt, 'Receipt contains TEST content')
    return receipt


@dataclass(frozen=True)
class SealedReceipt:
    root: Path
    reference: dict

    def verify(self):
        return validate_receipt(self.root, self.reference)


def load_receipt(root, spec):
    validate_receipt(root, spec)
    return SealedReceipt(Path(root), dict(spec))


def validate_test_capability(root, capability, manifest_path):
    require(isinstance(capability, dict), 'Final-evaluation capability missing')
    release = read(checked_file(root, capability['release']))
    receipt = validate_receipt(root, capability['receipt'])
    decision(release, 'final-evaluate')
    require(release['selection_sha256'] == capability['selection_sha256'] and
            release['checkpoint_sha256'] == capability['checkpoint_sha256'], 'Release not bound to frozen selection/model')
    require(sha(manifest_path) == receipt['manifest_sha256'] and
            release['receipt_sha256'] == capability['receipt']['sha256'], 'Sealed TEST manifest/receipt mismatch')
    return receipt
