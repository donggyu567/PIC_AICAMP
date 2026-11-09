"""Temporary unit-test evidence only. Never creates project data or human approvals."""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'experiments/koelectra_v2'))
from expanded_common import LABELS, REVISION, sha, write_json
from expanded_data import load_partition, load_receipt


def reference(root, path):
    return dict(path=path.relative_to(root).as_posix(), sha256=sha(path))


def tiny_model(seed):
    import torch
    from transformers import ElectraConfig, ElectraModel
    from risk_speech_ai.model import RiskSpeechClassifier
    torch.manual_seed(seed)
    config = ElectraConfig(vocab_size=35000, embedding_size=8, hidden_size=8,
                           intermediate_size=16, num_hidden_layers=1, num_attention_heads=2,
                           max_position_embeddings=512, hidden_dropout_prob=0., attention_probs_dropout_prob=0.)
    config._commit_hash = REVISION
    return RiskSpeechClassifier(ElectraModel(config))


def make_fixture(root):
    """All text is the same inert token. Mock evidence is labelled UNIT FIXTURE ONLY."""
    root = Path(root)
    split = dict(schema='expanded-split/1', frozen=True, conversations={})
    datasets = {}
    for role, count in [('train', 24), ('validation', 24), ('synthetic_train', 4)]:
        data = []
        for index in range(count):
            cid = f'FIXTURE_{role}_{index:03d}'
            item = dict(role=role, scenario_family_id=f'FAMILY_{role}_{index}',
                        source_id=f'SOURCE_{role}', author_id=f'AUTHOR_{role}')
            split['conversations'][cid] = item
            positive = index < count//2
            labels = []
            if positive:
                labels = ['institution_impersonation']
                if role == 'train':
                    labels = ['money_transfer'] if index < 6 else ['personal_information']
                    if index < 2:
                        labels.append('institution_impersonation')
                    if index == 0:
                        labels.append('app_installation')
                elif index < 4:
                    labels.append('money_transfer')
            data.append(dict(conversation_id=cid, utterance_id=1, text='가상 입력',
                             is_phishing=positive, labels=labels, hard_negative=not positive, origin='fixture',
                             **{k: v for k, v in item.items() if k != 'role'}))
        datasets[role] = data
    split_path = write_json(root / 'split.json', split)
    evidence = root / 'fixture-evidence.txt'
    evidence.write_text('UNIT FIXTURE ONLY. No real person approved any dataset.', encoding='utf-8')
    evidence_ref = reference(root, evidence)
    def mocked(purpose, by='fixture-custodian'):
        return dict(approved=True, purpose=purpose, by=by, at='2026-11-09T12:00:00+09:00',
                    evidence='UNIT FIXTURE ONLY', evidence_file=evidence_ref, rights_holder='UNIT FIXTURE ONLY')
    result = {}
    for role, data in datasets.items():
        data_path = root / f'{role}.jsonl'
        data_path.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in data), encoding='utf-8')
        keys = [f'{r["conversation_id"]}:1' for r in data]
        purpose = 'evaluation' if role == 'validation' else 'training'
        approval = dict(schema='expanded-approval/1', data_sha256=sha(data_path), split_sha256=sha(split_path),
                        preprocessing_version='fixture-masked-identity/1', scope_keys=keys,
                        permissions={f'SOURCE_{role}': mocked(purpose)},
                        reviews=[dict(**mocked('review', by), scope_keys=keys, unresolved=[])
                                 for by in ('김해린', '임정윤')],
                        final_agreement=mocked('final_agreement'), use_decision=mocked(purpose))
        approval_path = write_json(root / f'{role}-approval.json', approval)
        manifest = dict(schema='expanded-data/1', role=role, fixture=True, label_order=list(LABELS),
                        model_revision=REVISION, tokenizer_revision=REVISION,
                        preprocessing_version='fixture-masked-identity/1', data=reference(root, data_path),
                        split=reference(root, split_path), approval=reference(root, approval_path))
        manifest_path = write_json(root / f'{role}-manifest.json', manifest)
        result[role] = load_partition(root, manifest_path, role, fixture=True)
    receipt_path = write_json(root / 'test-receipt.json', dict(schema='sealed-test-receipt/1', sealed=True,
                     data_sha256='0'*64, manifest_sha256='1'*64, split_sha256=sha(split_path),
                     custodian=mocked('seal')))
    result['receipt'] = load_receipt(root, reference(root, receipt_path))
    return result


def predictions(partition, *, epoch=1, arm='B_ratio', offset=0.):
    return {seed: dict(schema='expanded-predictions/1', role=partition.role, seed=seed, epoch=epoch, arm=arm,
                       bindings=partition.bindings,
                       row_keys=[f'{r["conversation_id"]}:{r["utterance_id"]}' for r in partition.rows],
                       logits=[[2.+offset if r['is_phishing'] else -2.+offset] +
                               [2. if label in r['labels'] else -2. for label in LABELS] for r in partition.rows])
            for seed in (42, 43, 44)}
