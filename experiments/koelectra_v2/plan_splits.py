"""Propose group-isolated splits; never certify labels or alter source JSONL."""
from __future__ import annotations
import hashlib
import json
import random
import sys
import unicodedata
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "reports/v2_experiment_design"
OUTPUT = Path(__file__).resolve().parent
LABELS = ("institution_impersonation", "money_transfer", "personal_information", "app_installation",
          "secrecy", "threat_pressure", "loan_fraud", "information_probing")
SEED = 20261106
INPUT = ROOT / "artifacts/v1_recovered_8faa6a7eebfe/prepared"


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def load(path): return [json.loads(s) for s in path.read_text(encoding="utf-8").splitlines()]
def normalize(text):
    return "".join(c for c in unicodedata.normalize("NFKC",text).casefold() if not c.isspace() and not unicodedata.category(c).startswith("P"))
def write(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")


def components(labels,texts):
    ids=sorted({r["conversation_id"] for r in labels})
    parent={c:c for c in ids}; edges=[]
    def find(x):
        while parent[x]!=x: parent[x]=parent[parent[x]];x=parent[x]
        return x
    def join(a,b,kind,detail):
        if a==b:return
        edges.append(dict(left=a,right=b,kind=kind,detail=detail))
        parent[find(a)]=find(b)
    source=defaultdict(set); items=defaultdict(set); normalized=defaultdict(list)
    for r in labels:
        source[r["source"]].add(r["conversation_id"])
        # Item labels such as 'first recording' are scoped to their source.
        if r.get("source_item"):items[r["source"],r["source_item"]].add(r["conversation_id"])
    for kind,groups in (("shared_source_proxy",source),("shared_scoped_source_item",items)):
        for key,members in sorted(groups.items(),key=lambda x:str(x[0])):
            ordered=sorted(members)
            for c in ordered[1:]:join(ordered[0],c,kind,str(key))
    for r in texts: normalized[normalize(r["tuned_text"])].append(r)
    for text,rows in normalized.items():
        members=sorted({r["conversation_id"] for r in rows})
        for c in members[1:]:join(members[0],c,"normalized_equal_utterance",dict(normalized_text=text,utterance_ids=[f"{r['conversation_id']}-{r['utterance_id']}" for r in rows]))
    unique=list(normalized)
    near=[]
    for a,b in combinations(unique,2):
        if {r["conversation_id"] for r in normalized[a]}=={r["conversation_id"] for r in normalized[b]} and len({r["conversation_id"] for r in normalized[a]})==1:continue
        sm=SequenceMatcher(None,a,b,autojunk=False)
        if sm.real_quick_ratio()<.80 or sm.quick_ratio()<.80:continue
        # Symmetric maximum prevents direction-dependent missed candidates.
        score=max(sm.ratio(),SequenceMatcher(None,b,a,autojunk=False).ratio())
        if score<.80:continue
        for left in normalized[a]:
            for right in normalized[b]:
                if left["conversation_id"]==right["conversation_id"]:continue
                item=dict(left=f"{left['conversation_id']}-{left['utterance_id']}",right=f"{right['conversation_id']}-{right['utterance_id']}",
                          similarity=round(score,6),left_text=left["tuned_text"],right_text=right["tuned_text"])
                near.append(item);join(left["conversation_id"],right["conversation_id"],"near_utterance_080",item)
    transcripts=defaultdict(list)
    for r in texts:transcripts[r["conversation_id"]].append(r)
    full={c:normalize("\n".join(r["tuned_text"] for r in sorted(rows,key=lambda r:r["utterance_id"]))) for c,rows in transcripts.items()}
    for a,b in combinations(ids,2):
        sm=SequenceMatcher(None,full[a],full[b],autojunk=False)
        if sm.real_quick_ratio()<.80 or sm.quick_ratio()<.80:continue
        score=max(sm.ratio(),SequenceMatcher(None,full[b],full[a],autojunk=False).ratio())
        if score>=.80:join(a,b,"near_full_transcript_080",dict(similarity=round(score,6)))
    groups=defaultdict(list)
    for c in ids:groups[find(c)].append(c)
    ordered=sorted(groups.values(),key=lambda g:(-len(g),g))
    return {f"G{i:03}":g for i,g in enumerate(ordered,1)},edges,near


def summarize(ids,labels):
    rows=[r for r in labels if r["conversation_id"] in ids]
    return dict(conversations=len(ids),utterances=len(rows),phishing=sum(r["is_phishing"] for r in rows),
        entirely_normal_conversations=sum(not any(r['is_phishing'] for r in rows if r['conversation_id']==c) for c in ids),
        normal=sum(not r["is_phishing"] for r in rows),labels={l:sum(l in r["labels"] for r in rows) for l in LABELS},
        label_conversations={l:len({r["conversation_id"] for r in rows if l in r["labels"]}) for l in LABELS})


def assign(groups,labels,ratios=(.80,.10,.10),seed=SEED):
    """One seeded allocation using source/label support only, never predictions."""
    rng=random.Random(seed); group_ids=sorted(groups); rng.shuffle(group_ids)
    group_ids.sort(key=lambda k:-len(groups[k]))
    if len(group_ids)<3:raise ValueError("Fewer than three isolated components; cannot propose 3-way split")
    targets=dict(zip(("train","validation","test"),[len({r['conversation_id'] for r in labels})*p for p in ratios]))
    placement={group_ids[0]:"train"}; counts=Counter(train=len(groups[group_ids[0]]))
    positive_groups=[g for g in group_ids[1:] if summarize(set(groups[g]),labels)["phishing"]>0]
    # Before model fitting only: try to put one positive group into each holdout.
    for split in ("validation","test"):
        candidates=[g for g in positive_groups if g not in placement]
        g=min(candidates,key=lambda k:(len(groups[k]),group_ids.index(k))) if candidates else next(g for g in reversed(group_ids) if g not in placement)
        placement[g]=split;counts[split]+=len(groups[g])
    # A normal reply inside a scam is not a fully legitimate-call negative.
    # Reserve a wholly normal source component in each holdout when possible.
    normal_groups=[g for g in group_ids[1:] if summarize(set(groups[g]),labels)['phishing']==0]
    for split in ('validation','test'):
        candidates=[g for g in normal_groups if g not in placement]
        if candidates:
            g=min(candidates,key=lambda k:(len(groups[k]),group_ids.index(k)))
            placement[g]=split;counts[split]+=len(groups[g])
    for g in group_ids:
        if g in placement:continue
        split=max(("train","validation","test"),key=lambda s:(targets[s]-counts[s],-("train","validation","test").index(s)))
        placement[g]=split;counts[split]+=len(groups[g])
    assignment={c:placement[g] for g,members in groups.items() for c in members}
    return assignment,placement


def review_policy_groups(labels,edges):
    """Alternative proposal only: short normal turns need human exceptions.

    Never silently exempt a risky phrase. Same-source and whole-dialogue edges
    always remain. No exceptions are approved by this planning function.
    """
    ids=sorted({r['conversation_id'] for r in labels}); parent={c:c for c in ids}
    risk={f"{r['conversation_id']}-{r['utterance_id']}":r['is_phishing'] for r in labels}
    def find(x):
        while parent[x]!=x:parent[x]=parent[parent[x]];x=parent[x]
        return x
    deferred=[]
    for edge in edges:
        keep=True; detail=edge['detail']
        if edge['kind']=='normalized_equal_utterance':
            keep=len(detail['normalized_text'])>=20 or any(risk[key] for key in detail['utterance_ids'])
        elif edge['kind']=='near_utterance_080':
            keep=min(len(normalize(detail['left_text'])),len(normalize(detail['right_text'])))>=20 or risk[detail['left']] or risk[detail['right']]
        if keep:parent[find(edge['left'])]=find(edge['right'])
        else:deferred.append(edge)
    grouped=defaultdict(list)
    for c in ids:grouped[find(c)].append(c)
    return {f'R{i:03}':g for i,g in enumerate(sorted(grouped.values(),key=lambda g:(-len(g),g)),1)},deferred


def main():
    labels,texts=load(INPUT/"labels.jsonl"),load(INPUT/"tuned.jsonl")
    assert len(labels)==len(texts)==1460
    groups,edges,near=components(labels,texts)
    assignment,placement=assign(groups,labels)
    distribution={s:summarize({c for c,v in assignment.items() if v==s},labels) for s in ("train","validation","test")}
    check_edges=[e for e in edges if assignment[e["left"]]!=assignment[e["right"]]]
    assert not check_edges
    rare={l:dict(positive_utterances=sum(l in r["labels"] for r in labels),
                 positive_conversations=len({r["conversation_id"] for r in labels if l in r["labels"]}),
                 independent_components=[g for g,ids in groups.items() if any(l in r["labels"] and r["conversation_id"] in ids for r in labels)],
                 holdout_support={s:distribution[s]["labels"][l] for s in ("validation","test")}) for l in LABELS}
    blockers=[f"{s}: no binary positive or negative" for s in ("validation","test") if not distribution[s]["phishing"] or not distribution[s]["normal"]]
    blockers += [f"{s}:{l}: no positives; recall/F1/AUC not estimable" for s in ('validation','test') for l in LABELS if distribution[s]['labels'][l]==0]
    plan=dict(plan_version="v1-group-candidate-20261106",status="DRAFT_NOT_APPROVED_NOT_EVALUATION_GOLD",seed=SEED,
        requested_conversation_ratios=dict(train=.8,validation=.1,test=.1),training_authorized=False,model_selection_performed=False,
        source_sha256={p.name:sha(p) for p in (INPUT/"labels.jsonl",INPUT/"tuned.jsonl")},
        grouping_policy="same source proxy + scoped source_item + all normalized equal turns + symmetric SequenceMatcher >=0.80 turns/dialogues; transitive closure; no short-turn exemption",
        semantic_family_metadata="NOT_AVAILABLE; sources and lexical components are conservative proxies; human semantic review pending",
        component_count=len(groups),groups=groups,group_to_split=placement,conversation_to_split=assignment,distribution=distribution,
        rare_label_feasibility=rare,metric_feasibility_blockers=blockers,
        test_sealing="Planning statistics only, not model predictions; after human review freeze hashes and seal test. Source/test membership never enters optimizer or threshold selection.",
        evaluation_labels_human_verified=False,old_checkpoint_scope="No old checkpoint restored; candidate holdouts could be unseen only for freshly initialized retrained models using this plan.")
    write(OUTPUT/"split_candidate.json",plan)
    write(REPORTS/"grouping_evidence.json",dict(groups=groups,edge_count=len(edges),edges=edges,near_turn_candidates=near,cross_split_edge_count=0))
    relaxed,deferred=review_policy_groups(labels,edges)
    proposed,group_proposed=assign(relaxed,labels,ratios=(.70,.15,.15))
    rd={s:summarize({c for c,v in proposed.items() if v==s},labels) for s in ('train','validation','test')}
    exceptions=[e for e in deferred if proposed[e['left']]!=proposed[e['right']]]
    alternative=dict(plan,plan_version='v1-source-content-review-candidate-20261106',
        requested_conversation_ratios=dict(train=.70,validation=.15,test=.15),component_count=len(relaxed),groups=relaxed,
        group_to_split=group_proposed,conversation_to_split=proposed,distribution=rd,
        grouping_policy='same source/scoped item + all risky lexical duplicates + normal turns with >=20 normalized characters + whole-dialogue >=0.80; short normal turn exemptions PROPOSED ONLY',
        short_turn_exception_policy_human_approved=False,short_normal_edge_exception_count=len(exceptions),
        required_human_decisions='Approve or reject every deferred crossing short-normal edge; resolve semantic families and verify held-out labels before freezing.',
        rare_label_feasibility={l:dict(positive_utterances=sum(l in r['labels'] for r in labels),
            independent_components=[g for g,members in relaxed.items() if any(l in r['labels'] and r['conversation_id'] in members for r in labels)],
            holdout_support={s:rd[s]['labels'][l] for s in ('validation','test')}) for l in LABELS},
        metric_feasibility_blockers=[f"{s}:{l}: no positives; not estimable" for s in ('validation','test') for l in LABELS if rd[s]['labels'][l]==0])
    write(OUTPUT/'split_review_candidate.json',alternative)
    write(REPORTS/'short_normal_exceptions_pending.json',dict(status='NEEDS_HUMAN_REVIEW_NOT_APPROVED',
        proposed_rule='Only <20 normalized characters, both currently normal; no row removed or relabeled',edges=exceptions))
    print(json.dumps(dict(review_policy_components=len(relaxed),review_policy_distribution=rd,unapproved_crossing_exceptions=len(exceptions)),ensure_ascii=False,indent=2))
    print(json.dumps({k:plan[k] for k in ("component_count","distribution","rare_label_feasibility","metric_feasibility_blockers")},ensure_ascii=False,indent=2))


if __name__=="__main__":main()
