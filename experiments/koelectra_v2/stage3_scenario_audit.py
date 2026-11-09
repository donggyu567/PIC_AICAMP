"""Conversation-level lexical scenario screening; never reads sealed TEST."""
from collections import defaultdict
from itertools import combinations, product
from stage3_data import BASE, REPORT, V1_TEXT, AUX, jsonl, normalize
from expanded_common import write_json, sha


def shingles(text):
    return {text[i:i+3] for i in range(max(0,len(text)-2))}


def screen(left, right=None, threshold=.30):
    pairs = combinations(left, 2) if right is None else product(left, right)
    hits = []; count = 0
    for (aid,a), (bid,b) in pairs:
        count += 1
        score = len(a & b)/len(a | b) if a | b else 1.
        if score >= threshold:
            hits.append(dict(left=aid, right=bid, jaccard_3gram=round(score,6)))
    return dict(comparisons=count, threshold=threshold, candidates=hits, candidate_count=len(hits))


def conversations(records):
    return [(c.get('conversation_id',c.get('synthetic_id')), shingles(normalize(' '.join(u['text'] for u in c['utterances'])))) for c in records]


if __name__ == '__main__':
    train = conversations(jsonl(BASE/'train_80_candidate.jsonl'))
    val = conversations(jsonl(BASE/'validation_32_synthetic.jsonl'))
    grouped = defaultdict(list)
    for row in jsonl(V1_TEXT): grouped[row['conversation_id']].append(row['tuned_text'])
    v1 = [(cid,shingles(normalize(' '.join(values)))) for cid,values in grouped.items()]
    aux = conversations(jsonl(AUX))
    checks = dict(train_internal=screen(train), validation_internal=screen(val), train_vs_validation=screen(train,val),
        train_vs_v1=screen(train,v1), validation_vs_v1=screen(val,v1), train_vs_aux=screen(train,aux), validation_vs_aux=screen(val,aux))
    write_json(REPORT/'scenario_lexical_audit.json', dict(schema='scenario-lexical-screen/1', method='Jaccard of normalized whole-dialogue character trigrams',
        checks=checks, semantic_independence='NOT_VERIFIED', test_body_access=False,
        limit='Lexical heuristics can miss paraphrases and repeated scenario mechanisms. Distinct family keys do not certify semantic independence.',
        train_sha256=sha(BASE/'train_80_candidate.jsonl'), validation_sha256=sha(BASE/'validation_32_synthetic.jsonl')))
    print({key:value['candidate_count'] for key,value in checks.items()}, flush=True)
