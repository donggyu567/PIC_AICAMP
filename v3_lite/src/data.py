"""Explicit TRAIN/VALIDATION files, evidence-bound reviews, causal v2 samples."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
import json
from pathlib import Path
import re
import unicodedata

from .common import (BUNDLE, DATA, V2, LABELS, FOCUS, GateError, bootstrap, digest, inside,
                     read_json, require, sha)

FILES = {'train': 'train_additions.jsonl', 'validation': 'validation_new.jsonl'}
CATEGORIES = {'financial', 'official', 'identity', 'app', 'quotation'}
MASKS = {'PERSON', 'PHONE_NUMBER', 'ACCOUNT_NUMBER', 'CARD_NUMBER', 'ADDRESS', 'RRN', 'BIRTH', 'EMAIL', 'PW'}
BASE = V2 / 'dataset/04. processed/v2_internal_20261109_v1'


def allowed_role(role):
    require(role in FILES, 'Only TRAIN/VALIDATION allowed; TEST denied before IO')


def evidence_file(base, spec):
    require(isinstance(spec, dict) and set(spec) == {'path', 'sha256'}, 'Evidence needs path/SHA')
    name = spec['path']
    require(isinstance(name, str) and ':' not in name and '\\' not in name and
            not Path(name).is_absolute() and '..' not in Path(name).parts and
            'test' not in name.lower() and '.sealed' not in name.lower(), 'Forbidden evidence path')
    path = inside(Path(base) / name, DATA)
    require(path.is_relative_to(Path(base).resolve()), 'Evidence escapes its version directory')
    require(path.is_file() and sha(path) == spec['sha256'], f'Evidence missing/hash mismatch: {name}')
    return path


def jsonl(path):
    # Duplicate/nonfinite keys are checked using the common JSON parser on each line.
    def pairs(items):
        result = {}
        for k, v in items:
            require(k not in result, 'Duplicate JSONL key')
            result[k] = v
        return result
    return [json.loads(line, object_pairs_hook=pairs,
                       parse_constant=lambda x: (_ for _ in ()).throw(GateError('Nonfinite JSONL')))
            for line in Path(path).read_text(encoding='utf-8-sig').splitlines() if line.strip()]


def load_manifest(path):
    path = inside(path, DATA)
    require(path.name == 'manifest.json', 'Use a versioned manifest.json')
    m = read_json(path)
    require(m.get('schema') == 'v3-lite-data/1' and m.get('purpose') == 'internal_experiment', 'Wrong data schema/purpose')
    require(m.get('artifact_kind') == 'research_corpus', 'Fixtures cannot authorize real training')
    require(m.get('label_order') == list(LABELS), 'Data label order mismatch')
    require(m.get('production_training_authorized') is False and m.get('deployment_approved') is False,
            'This entry point never authorizes production training')
    require(set(m.get('splits', {})) == {'train', 'validation'}, 'No TEST references permitted')
    for role, name in FILES.items():
        require(m['splits'][role]['path'] == name, f'Unexpected {role} filename')
    require(m.get('no_v2_test_derivation') is True, 'No TEST derivation declaration missing')
    return m


def utterance_binding(c, u):
    return digest(dict(conversation_id=c['conversation_id'], family_id=c.get('family_id', c.get('scenario_family_id')),
                       utterance_id=u['utterance_id'], speaker=u['speaker'], text=u['text'],
                       is_phishing=u['is_phishing'], labels=u['labels']))


def validate_reviews(conversations, reviews, *, required_keys=None):
    """Attestations are evidence, not generated approval; verify every reviewed target binding."""
    by_key = {}
    for r in reviews:
        key = (r.get('conversation_id'), r.get('utterance_id'))
        require(key not in by_key, 'Duplicate review key')
        by_key[key] = r
    needed = required_keys if required_keys is not None else {
        (c['conversation_id'], u['utterance_id']) for c in conversations for u in c['utterances']}
    for c in conversations:
        for u in c['utterances']:
            key = (c['conversation_id'], u['utterance_id'])
            if key not in needed:
                continue
            require(key in by_key, f'Missing independent review: {key}')
            review = by_key[key]
            require(review.get('record_type') == 'human_review' and review.get('status') == 'resolved', 'Human review unresolved/fixture-only')
            require(review.get('content_sha256') == utterance_binding(c, u), 'Review does not bind current content/labels')
            raters = review.get('reviewers', [])
            require(len(raters) == 2 and len({a.get('reviewer_id') for a in raters}) == 2, 'Two distinct reviewers required')
            actual = dict(is_phishing=u['is_phishing'], labels=u['labels'])
            for a in raters:
                require(isinstance(a.get('reviewer_id'), str) and a['reviewer_id'].strip() and
                        a.get('human') is True and a.get('independent') is True and a.get('reviewed_at'),
                        'Human/independence/time attestation absent')
                require(datetime.fromisoformat(a['reviewed_at']).tzinfo is not None, 'Review timestamp needs timezone')
                al=a.get('labels')
                require(isinstance(al,list) and all(l in LABELS for l in al) and type(a.get('is_phishing')) is bool and
                        al==sorted(set(al),key=LABELS.index) and a['is_phishing']==bool(al), 'Reviewer labels invalid')
            agreement = all(dict(is_phishing=a['is_phishing'], labels=a['labels']) == actual for a in raters)
            if not agreement:
                decision = review.get('resolution', {})
                require(decision.get('adjudicator_id') and decision.get('reason') and decision.get('resolved_at') and
                        decision.get('is_phishing') == actual['is_phishing'] and decision.get('labels') == actual['labels'],
                        'Disagreement lacks a bound resolution')
                require(datetime.fromisoformat(decision['resolved_at']).tzinfo is not None, 'Resolution needs timezone')


def validate_rights(c, record, role):
    require(record.get('record_type')=='data_use_authorization' and record.get('status')=='confirmed' and
            c['source'] in record.get('source_ids',[]) and role in record.get('permitted_uses',[]) and
            record.get('authorized_by') and record.get('authorized_at') and record.get('basis'),
            'Source rights evidence lacks authority/scope/source binding')
    require(datetime.fromisoformat(record['authorized_at']).tzinfo is not None, 'Rights timestamp needs timezone')


def validate_schema(conversations, role):
    allowed_role(role)
    require(bool(conversations), 'Empty corpus')
    ids, families, texts = set(), set(), set()
    for c in conversations:
        cid, family = c.get('conversation_id'), c.get('family_id')
        require(isinstance(cid, str) and cid.startswith('V3-') and 'TEST' not in cid.upper(), 'New V3 conversation ID required')
        require(cid not in ids and isinstance(family, str) and family and family not in families and 'TEST' not in family.upper(), 'Duplicate/invalid conversation/family')
        ids.add(cid); families.add(family)
        require(c.get('split') == role and c.get('review_status') == 'reviewed', 'Wrong split/unreviewed conversation')
        require(isinstance(c.get('source'), str) and c['source'].strip(), 'Source missing')
        provenance = c.get('provenance', {})
        require(all(provenance.get(k) for k in ['method', 'author_or_generator', 'created_at', 'origin_id', 'semantic_family_id']), 'Provenance missing')
        origin=str(provenance['origin_id']).upper()
        require('TEST' not in origin and 'SYN2-' not in origin and 'SYN3-' not in origin and
                provenance.get('test_derived', False) is False, 'New data must not derive from v2 examples/TEST')
        rights = c.get('rights', {})
        require(rights.get('status') == 'documented' and role in rights.get('permitted_uses', []) and rights.get('evidence'), 'Use rights missing')
        require(c.get('category') in CATEGORIES, 'Hard-negative/scenario category missing')
        us = c.get('utterances', [])
        require(len(us) == 8, 'Each new conversation needs eight utterances')
        for i, u in enumerate(us, 1):
            require(type(u.get('utterance_id')) is int and u['utterance_id'] == i, 'Duplicate/reordered utterance ID')
            require(u.get('speaker') in ('speaker_A', 'speaker_B'), 'Unknown speaker')
            text = u.get('text')
            require(isinstance(text, str) and text.strip() and 'history' not in u, 'Only current text; histories are computed')
            require(not re.search(r'(?:\d[ -]?){7,}|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|https?://', text), 'Unmasked numeric/contact/URL candidate')
            require(all(t in MASKS for t in re.findall(r'\[([A-Z_]+)\]', text)), 'Unknown masking token')
            require(u.get('masking_reviewed') is True, 'Masking requires explicit human check')
            labels = u.get('labels')
            require(isinstance(labels, list) and all(t in LABELS for t in labels) and labels == sorted(set(labels), key=LABELS.index), 'Labels/order invalid')
            require(type(u.get('is_phishing')) is bool and u['is_phishing'] == bool(labels), 'Risk/type mismatch')
        textkey=normalized(' '.join(u['text'] for u in us))
        require(textkey not in texts, 'Duplicate conversation text under different IDs')
        texts.add(textkey)
    return statistics(conversations)


def statistics(conversations):
    rows = [u for c in conversations for u in c['utterances']]
    return dict(conversations=len(conversations), families=len({c.get('family_id', c.get('scenario_family_id')) for c in conversations}),
                utterances=len(rows), risk_positive=sum(u['is_phishing'] for u in rows),
                normal_conversations=sum(not any(u['is_phishing'] for u in c['utterances']) for c in conversations),
                types={l:dict(positive=sum(l in u['labels'] for u in rows), negative=sum(l not in u['labels'] for u in rows),
                              positive_families=len({c.get('family_id', c.get('scenario_family_id')) for c in conversations if any(l in u['labels'] for u in c['utterances'])})) for l in LABELS})


def normalized(text):
    return ''.join(c for c in unicodedata.normalize('NFKC', text).casefold() if c.isalnum())


def check_disjoint(*partitions):
    """Exact/near lexical screening complements evidence of semantic independence."""
    seen_ids, seen_family, seen_semantic = set(), set(), set()
    for cs in partitions:
        ids = {c['conversation_id'] for c in cs}
        families = {c.get('family_id', c.get('scenario_family_id')) for c in cs}
        semantic = {c.get('provenance', {}).get('semantic_family_id', c.get('family_id', c.get('scenario_family_id'))) for c in cs}
        require(not ids & seen_ids and not families & seen_family and not semantic & seen_semantic, 'Conversation/family/semantic-family overlap')
        require(len(semantic) == len(cs), 'Multiple conversations claim the same semantic family')
        seen_ids |= ids; seen_family |= families; seen_semantic |= semantic
    for i, left in enumerate(partitions):
        for right in partitions[i+1:]:
            for a in left:
                x = normalized(' '.join(u['text'] for u in a['utterances']))
                for b in right:
                    y = normalized(' '.join(u['text'] for u in b['utterances']))
                    require(SequenceMatcher(None, x, y, autojunk=False).ratio() < .8, 'Cross-partition near-duplicate: revise or independently adjudicate before freezing')


@dataclass(frozen=True)
class Partition:
    role: str
    conversations: tuple
    data_sha256: str
    source_path: str

    def rows(self):
        return [dict(u, conversation_id=c['conversation_id'], scenario_family_id=c.get('family_id', c.get('scenario_family_id')),
                     source_id=c.get('source', 'V2_INHERITED_SYNTHETIC'), category=c.get('category', 'legacy'),
                     hard_negative=not any(v['is_phishing'] for v in c['utterances'])) for c in self.conversations for u in c['utterances']]

    def samples(self):
        bootstrap()
        from stage3_research import causal_samples
        return causal_samples(self.conversations)


def load_split(role, manifest_path):
    allowed_role(role)  # Must precede any manifest/path IO.
    path = inside(manifest_path, DATA)
    m = load_manifest(path)
    file = evidence_file(path.parent, m['splits'][role])
    cs = jsonl(file)
    validate_schema(cs, role)
    for c in cs:
        validate_rights(c,read_json(evidence_file(path.parent,c['rights']['evidence'])),role)
    reviews = jsonl(evidence_file(path.parent, m['reviews'][role]))
    validate_reviews(cs, reviews)
    return Partition(role, tuple(cs), sha(file), str(file))


def load_legacy(role):
    allowed_role(role)
    bootstrap()
    bundle = read_json(BUNDLE / 'bundle_manifest.json')
    path = BASE / {'train': 'train_80_candidate.jsonl', 'validation': 'validation_32_synthetic.jsonl'}[role]
    require(sha(path) == bundle['bindings'][role + '_sha256'], 'Original v2 data changed')
    return Partition(role, tuple(jsonl(path)), sha(path), str(path))


def load_training_inputs(manifest_path):
    path = inside(manifest_path, DATA)
    m = load_manifest(path)
    train, validation = load_split('train', path), load_split('validation', path)
    original, old_val = load_legacy('train'), load_legacy('validation')
    cs = list(original.conversations)
    required = {(c['conversation_id'], u['utterance_id']) for c in cs for u in c['utterances']
                if any(l in u['labels'] for l in FOCUS) or not any(v['is_phishing'] for v in c['utterances'])}
    validate_reviews(cs, jsonl(evidence_file(path.parent, m['reviews']['legacy_focus'])), required_keys=required)
    split_review = read_json(evidence_file(path.parent, m['split_review']))
    bindings = dict(train=train.data_sha256, validation=validation.data_sha256,
                    legacy_train=original.data_sha256, legacy_validation=old_val.data_sha256)
    require(split_review.get('record_type') == 'human_split_review' and split_review.get('status') == 'resolved' and
            split_review.get('reviewed_at') and split_review.get('bindings') == bindings and split_review.get('no_test_derivation') is True and
            split_review.get('semantic_independence_reviewed') is True and len(set(split_review.get('human_reviewer_ids', []))) == 2,
            'Independent split review missing/unbound')
    check_disjoint(train.conversations, validation.conversations, original.conversations, old_val.conversations)
    for part, nc, nu, normal in [(train, 24, 192, 12), (validation, 32, 256, 12)]:
        s = statistics(part.conversations)
        require((s['conversations'], s['utterances'], s['normal_conversations']) == (nc, nu, normal), 'Planned corpus counts not met')
        for l in FOCUS:
            require(s['types'][l]['positive'] >= 18 and s['types'][l]['positive_families'] >= 6, 'Focus support insufficient')
    new_stats = statistics(validation.conversations)
    for part in [train, validation]:
        categories=Counter(c['category'] for c in part.conversations if not any(u['is_phishing'] for u in c['utterances']))
        required_categories=dict(financial=3,official=2,identity=3,app=2,quotation=2) if part.role=='train' else dict.fromkeys(CATEGORIES,1)
        require(all(categories[k]>=n for k,n in required_categories.items()), 'Normal scenario category coverage insufficient')
    for l in LABELS:
        require(new_stats['types'][l]['positive'] > 0, 'Validation lacks an output label')
    all_train = tuple(cs) + train.conversations
    require(sum(len(c['utterances']) for c in all_train) == 848, 'TRAIN budget changed')
    return Partition('train', all_train, digest(bindings), str(path)), validation, old_val, bindings
