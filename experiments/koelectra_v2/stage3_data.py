"""Versioned internal-experiment corpus; no optimizer, human approvals or TEST loader."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
from difflib import SequenceMatcher
import hashlib
import json
from pathlib import Path
import re
import subprocess
import unicodedata

from expanded_common import ROOT, LABELS, require, sha, read, write_json, publish, digest

BASE = ROOT/'dataset/04. processed/v2_internal_20261109_v1'
REPORT = ROOT/'reports/v2_stage3_20261109'
AUTHORED = BASE/'authoring'
OLD_TRAIN = ROOT/'dataset/04. processed/v2_train_expansion/train_24_mixed_review_candidate.jsonl'
AUX = ROOT/'dataset/04. processed/v2_validation/validation_24_generated.jsonl'
V1_TEXT = ROOT/'artifacts/v1_recovered_8faa6a7eebfe/prepared/tuned.jsonl'
V1_LABELS = ROOT/'artifacts/v1_recovered_8faa6a7eebfe/prepared/labels.jsonl'
CODES = dict(zip('IMPASTLF', LABELS))  # I institution, M money, P personal, A app, S secrecy, T threat, L loan, F probing
ALLOWED = {'PERSON','PHONE_NUMBER','ACCOUNT_NUMBER','CARD_NUMBER','ADDRESS','RRN','BIRTH','EMAIL','PW'}
MODEL = {'observed_identity': 'Codex (GPT-6 family)', 'requested_model': 'GPT-6.1 Sol',
         'exact_backend_model_id': None, 'identity_limit': 'Backend model ID is not exposed; requested model is not asserted as actual',
         'method': 'AI session authored individual dialogue literals; Python only serializes and validates'}


def jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines() if line.strip()]


def put_jsonl(path, records):
    data = ''.join(json.dumps(r, ensure_ascii=False, separators=(',', ':'))+'\n' for r in records).encode()
    publish(path, lambda stream: stream.write(data))


def normalize(text):
    return ''.join(c for c in unicodedata.normalize('NFKC', text).casefold()
                   if not c.isspace() and not unicodedata.category(c).startswith('P'))


def parse_batch(path):
    """@ split|number|primary code or N|family slug|context. Then speaker|codes|literal."""
    conversations = []
    current = None
    for raw in Path(path).read_text(encoding='utf-8-sig').splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith('@ '):
            split, number, primary, family, context = line[2:].split('|', 4)
            cid = f'SYN3-{split.upper()}-{int(number):04d}'
            current = dict(conversation_id=cid, synthetic_id=cid, split=split,
                scenario_family_id=f'FAM3-{split.upper()}-{family}', scenario_id=f'SCN3-{split.upper()}-{family}',
                primary_type=None if primary == 'N' else CODES[primary], scenario_summary=context,
                source_kind='llm_synthetic', actual_call=False, data_purpose='internal_experiment',
                label_status='provisional', human_review_complete=False, deployment_approved=False,
                generation=dict(**MODEL, batch_id=Path(path).stem, source_sha256=sha(path),
                                authored_event_at=datetime.now(timezone.utc).isoformat()), utterances=[])
            conversations.append(current)
        else:
            require(current is not None, 'Dialogue header missing')
            speaker, labels, text = line.split('|', 2)
            labels = [] if labels == '-' else [CODES[code] for code in labels]
            labels.sort(key=LABELS.index)
            current['utterances'].append(dict(utterance_id=len(current['utterances'])+1,
                speaker={'A':'speaker_A','B':'speaker_B'}[speaker], text=text, is_phishing=bool(labels), labels=labels,
                label_rationale='현재 발화의 ' + ', '.join(labels) + ' 행위에 대한 AI 잠정 라벨' if labels else
                                '현재 발화에 직접적인 위험 행위가 없는 AI 잠정 정상 라벨'))
    return conversations


def validate(conversations, *, expected=None):
    if expected is not None:
        require(len(conversations) == expected, f'Expected {expected} conversations, got {len(conversations)}')
    ids, families, keys = set(), set(), set()
    for c in conversations:
        require(c['split'] in ('train','validation','test'), 'Unknown role')
        require(c['conversation_id'] not in ids and c['scenario_family_id'] not in families, 'Duplicate ID/family')
        ids.add(c['conversation_id']); families.add(c['scenario_family_id'])
        require(c['source_kind'] == 'llm_synthetic' and c['data_purpose'] == 'internal_experiment', 'Provenance/purpose mismatch')
        require(c['label_status'] == 'provisional' and c['deployment_approved'] is False, 'False approval')
        require(8 <= len(c['utterances']) <= 10, 'Conversation length outside 8..10')
        for index, u in enumerate(c['utterances'], 1):
            require(u['utterance_id'] == index and u['speaker'] in ('speaker_A','speaker_B'), 'Utterance identity invalid')
            require(type(u['is_phishing']) is bool and u['is_phishing'] == bool(u['labels']), 'Binary/type target disagreement')
            require(len(u['labels']) == len(set(u['labels'])) and set(u['labels']) <= set(LABELS), 'Unknown/duplicate labels')
            if 'legacy_provenance' not in c:
                require(u['labels'] == sorted(u['labels'], key=LABELS.index), 'New label list order changed')
                require(len(u['labels']) <= 2, 'Overloaded multi-label utterance')
            text = u['text']
            require(isinstance(text, str) and text.strip(), 'Empty text')
            require(not re.search(r'https?://|www\.|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|(?:\d[ -]?){7,}', text), 'Literal sensitive identifier/link')
            require(set(re.findall(r'\[([^\]]+)\]', text)) <= ALLOWED, 'Unknown masking token')
            key = (c['conversation_id'], index)
            require(key not in keys, 'Duplicate sample key')
            keys.add(key)
    return stats(conversations)


def stats(conversations):
    utterances = [u for c in conversations for u in c['utterances']]
    positive = Counter(label for u in utterances for label in u['labels'])
    return dict(conversations=len(conversations), utterances=len(utterances),
                phishing=sum(u['is_phishing'] for u in utterances), normal=sum(not u['is_phishing'] for u in utterances),
                entirely_normal_conversations=sum(not any(u['is_phishing'] for u in c['utterances']) for c in conversations),
                multilabel_utterances=sum(len(u['labels']) > 1 for u in utterances),
                positive_labels={label: positive[label] for label in LABELS},
                positive_families={label: len({c['scenario_family_id'] for c in conversations
                    if any(label in u['labels'] for u in c['utterances'])}) for label in LABELS},
                semantic_independence='NOT_HUMAN_VERIFIED', label_accuracy='PROVISIONAL_NOT_HUMAN_VERIFIED')


def legacy_train():
    result = []
    for original in jsonl(OLD_TRAIN):
        c = dict(original)
        c.update(conversation_id=original['synthetic_id'], source_kind='llm_synthetic', data_purpose='internal_experiment',
                 label_status='provisional', deployment_approved=False,
                 legacy_provenance=dict(source_path=OLD_TRAIN.relative_to(ROOT).as_posix(), source_sha256=sha(OLD_TRAIN),
                     original_source_kind=original['source_kind'], original_generation_model=original.get('generation_model'),
                     original_record_sha256=digest(original)))
        # Existing review_preparation/revision_history and utterances are unchanged.
        result.append(c)
    return result


def texts(conversations):
    return [(f"{c['conversation_id']}:{u['utterance_id']}", normalize(u['text']))
            for c in conversations for u in c['utterances']]


def compare(left, right, *, within=False, threshold=.80):
    """Full candidate inventory without plaintext in reports (safe for TEST sealing)."""
    candidates = []
    comparisons = 0
    for i, (lid, a) in enumerate(left):
        for j, (rid, b) in enumerate(right):
            if within and j <= i:
                continue
            comparisons += 1
            if a == b:
                ratio = 1.
            else:
                matcher = SequenceMatcher(None, a, b, autojunk=False)
                if matcher.real_quick_ratio() < threshold or matcher.quick_ratio() < threshold:
                    continue
                ratio = matcher.ratio()
            if ratio >= threshold:
                candidates.append(dict(left=lid, right=rid, similarity=round(ratio, 6),
                                       normalized_length=[len(a), len(b)],
                                       kind='exact_normalized' if a == b else 'similar_ge_080'))
    return dict(pairs=comparisons, threshold=threshold, candidates=candidates, candidate_count=len(candidates),
                limit='Lexical screen only, not semantic independence proof')


def all_public():
    batches = sorted((BASE/'batches').glob('train_*.jsonl')) + sorted((BASE/'batches').glob('validation_*.jsonl'))
    return legacy_train() + [c for path in batches for c in jsonl(path)]


def batch(path):
    records = parse_batch(path)
    summary = validate(records, expected=8)
    role = records[0]['split']
    require(all(c['split'] == role for c in records), 'Batch mixes roles')
    existing = all_public()
    require(not {c['scenario_family_id'] for c in records} & {c['scenario_family_id'] for c in existing}, 'Family already reserved')
    prior = compare(texts(records), texts(existing))
    internal = compare(texts(records), texts(records), within=True)
    output = BASE/'batches'/f'{Path(path).stem}.jsonl'
    require(role != 'test', 'TEST authoring is handled only by the custodian sealing command')
    put_jsonl(output, records)
    write_json(REPORT/'batches'/f'{Path(path).stem}.json', dict(status='PASS_STRUCTURE_PENDING_SEMANTIC_REVIEW',
        source_sha256=sha(path), output_sha256=sha(output), stats=summary,
        against_existing=prior, within_batch=internal, human_approved=False))
    print(Path(path).stem, summary['conversations'], summary['utterances'],
          'lexical candidates', prior['candidate_count'], internal['candidate_count'], flush=True)


def capture():
    tracked = subprocess.check_output(['git','ls-files','-z'], cwd=ROOT).decode().split('\0')
    untracked = subprocess.check_output(['git','ls-files','--others','--exclude-standard','-z'], cwd=ROOT).decode().split('\0')
    paths = [p for p in tracked+untracked if p and not p.startswith(('reports/v2_stage3_20261109/',
                  'dataset/04. processed/v2_internal_20261109_v1/', 'experiments/koelectra_v2/stage3_'))]
    write_json(REPORT/'preservation_before.json', {p: sha(ROOT/p) for p in paths})


def finalize():
    train = legacy_train() + [c for p in sorted((BASE/'batches').glob('train_*.jsonl')) for c in jsonl(p)]
    validation = [c for p in sorted((BASE/'batches').glob('validation_*.jsonl')) for c in jsonl(p)]
    validate(train, expected=80); validate(validation, expected=32)
    require(not {c['scenario_family_id'] for c in train} & {c['scenario_family_id'] for c in validation}, 'Role family overlap')
    put_jsonl(BASE/'train_80_candidate.jsonl', train)
    put_jsonl(BASE/'validation_32_synthetic.jsonl', validation)
    registry = [dict(conversation_id=c['conversation_id'], split=c['split'], scenario_family_id=c['scenario_family_id'],
                     primary_type=c['primary_type'], summary=c.get('scenario_summary'),
                     model=c.get('generation', c.get('legacy_provenance')), semantic_review='PENDING') for c in train+validation]
    write_json(BASE/'scenario_registry.json', dict(schema='internal-scenario-registry/1', scenarios=registry,
        shared_ai_author=True, independent_human_authorship=False, source_model_independence=False))
    v1 = [(f"{r['conversation_id']}:{r['utterance_id']}", normalize(r['tuned_text'])) for r in jsonl(V1_TEXT)]
    aux = [dict(c, conversation_id=c['synthetic_id']) for c in jsonl(AUX)]
    checks = dict(train_internal=compare(texts(train), texts(train), within=True),
                  validation_internal=compare(texts(validation), texts(validation), within=True),
                  train_vs_validation=compare(texts(train), texts(validation)),
                  train_vs_v1=compare(texts(train), v1), validation_vs_v1=compare(texts(validation), v1),
                  train_vs_aux=compare(texts(train), texts(aux)), validation_vs_aux=compare(texts(validation), texts(aux)))
    write_json(REPORT/'quality.json', dict(schema='internal-quality-report/1', label_order=list(LABELS),
        train=stats(train), validation=stats(validation), duplicate_checks=checks,
        future_context_used_for_automatic_labels=False, causal_label_accuracy='NOT_INDEPENDENTLY_VERIFIED',
        old_train_internal_duplicate_retained=True, v1_training_included=False, v1_exclusion='usage rights not reverified'))
    write_json(BASE/'data_use_manifest.json', dict(schema='internal-research-data/1', purpose='internal_experiment',
        source_kind='llm_synthetic', label_order=list(LABELS), generation_model=MODEL,
        train=dict(path='train_80_candidate.jsonl', sha256=sha(BASE/'train_80_candidate.jsonl')),
        validation=dict(path='validation_32_synthetic.jsonl', sha256=sha(BASE/'validation_32_synthetic.jsonl')),
        registry_sha256=sha(BASE/'scenario_registry.json'),
        human_review_complete=False, deployment_approved=False, production_training_authorized=False,
        research_preflight_allowed=True, research_training_requires_explicit_phase4_mode=True,
        legacy_aux_validation=dict(path=AUX.relative_to(ROOT).as_posix(), sha256=sha(AUX), role='auxiliary_only'),
        v1=dict(labels_path=V1_LABELS.relative_to(ROOT).as_posix(), labels_sha256=sha(V1_LABELS),
                text_path=V1_TEXT.relative_to(ROOT).as_posix(), text_sha256=sha(V1_TEXT), included=False,
                reason='No new usage-rights approval is inferred from historical training')))
    print('PUBLIC FINALIZED', len(train), len(validation), flush=True)


def cpu():
    from expanded_assets import load_tokenizer
    from risk_speech_ai.dataset import RiskSpeechDataset, make_training_dataloader
    from risk_speech_ai.training_data import TrainingSample
    from risk_speech_ai.labels import to_multi_hot
    import torch
    tok = load_tokenizer()
    results = {}
    for role, path in [('train', BASE/'train_80_candidate.jsonl'), ('validation', BASE/'validation_32_synthetic.jsonl')]:
        convs = jsonl(path); validate(convs)
        samples = []
        for c in convs:
            for i, u in enumerate(c['utterances']):
                samples.append(TrainingSample(c['conversation_id'], u['utterance_id'],
                    [h['text'] for h in c['utterances'][max(0,i-5):i]], u['text'], float(u['is_phishing']), to_multi_hot(u['labels'])))
        loader = make_training_dataloader(RiskSpeechDataset(samples, tokenizer=tok), tokenizer=tok, batch_size=8, shuffle=False)
        seen = batches = maximum = 0
        for b in loader:
            n, width = b['input_ids'].shape
            require(width <= 512 and all(v.device.type == 'cpu' for v in b.values()), 'Tensor device/width failed')
            require(all(b[k].dtype == torch.int64 and b[k].shape == (n,width) for k in ('input_ids','attention_mask','token_type_ids')), 'Input tensor contract failed')
            require(b['risk_target'].shape == (n,1) and b['type_targets'].shape == (n,8), 'Target shape failed')
            require(b['risk_target'].dtype == b['type_targets'].dtype == torch.float32, 'Target dtype failed')
            require(torch.equal(b['type_targets'], torch.tensor([s.type_targets for s in samples[seen:seen+n]], dtype=torch.float32)), 'Target alignment failed')
            require(torch.equal(b['risk_target'], torch.tensor([[s.risk_target] for s in samples[seen:seen+n]], dtype=torch.float32)), 'Risk alignment failed')
            seen += n; batches += 1; maximum = max(maximum, width)
        results[role] = dict(samples=seen, batches=batches, max_tokens=maximum, max_history=max(len(s.history_texts) for s in samples),
                             optimizer_updates=0, human_approved=False, mode='explicit_internal_research_preflight')
    write_json(REPORT/'cpu_dataloader.json', dict(status='PASS', partitions=results, test_access=False,
        model_forward=False, training_executed=False, production_gate_unchanged=True))
    print('CPU', results, flush=True)


def preserve():
    before = read(REPORT/'preservation_before.json')
    changed = [p for p, value in before.items() if sha(ROOT/p) != value]
    require(not changed, 'Preexisting files changed')
    weights = read(ROOT/'reports/v2_stage1_20261109/inventory.json')['local_weight_inventory']
    require(all(sha(ROOT.parents[1]/item['root']/item['path']) == item['sha256'] for item in weights), 'Original weights changed')
    write_json(REPORT/'preservation.json', dict(status='PASS', files=len(before), changed=changed,
               weight_files=len(weights), checkpoint_weights_unchanged=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['capture','batch','finalize','cpu','preserve'])
    parser.add_argument('--source', type=Path)
    args = parser.parse_args()
    {'capture':capture,'batch':lambda:batch(args.source),'finalize':finalize,'cpu':cpu,'preserve':preserve}[args.mode]()
