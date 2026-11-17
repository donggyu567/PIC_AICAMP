"""Explicit unreviewed synthetic research route; never an authorized corpus."""
from __future__ import annotations
from collections import Counter
from pathlib import Path
import re

from .common import DATA,LABELS,V2,create_json,digest,inside,read_json,require,sha
from .data import (CATEGORIES,MASKS,Partition,allowed_role,check_disjoint,evidence_file,
                   jsonl,load_legacy,normalized,statistics)

POLICY_FIELDS=dict(purpose='internal_experiment',source_kind='llm_synthetic',human_reviewed=False,
                   human_review_complete=False,approved_for_production=False,deployment_allowed=False)

def test_origin(value):
    return bool(re.search(r'(?:^|[-_])TEST(?:[-_]|$)',str(value),flags=re.I))


def validate_research(conversations, role):
    allowed_role(role)
    require(bool(conversations),'Research corpus empty')
    ids=set(); families=set(); texts=set()
    for c in conversations:
        require(all(c.get(k)==v and type(c.get(k))==type(v) for k,v in POLICY_FIELDS.items()),'Research provenance/approval flags invalid')
        require(c.get('review_status')=='ai_provisional' and c.get('label_status')=='provisional','Never assert human-reviewed labels')
        cid=c.get('conversation_id'); fam=c.get('family_id')
        require(isinstance(cid,str) and cid.startswith('V3-') and not test_origin(cid) and cid not in ids,'Invalid/duplicate research ID')
        require(isinstance(fam,str) and fam and not test_origin(fam) and fam not in families,'Invalid/duplicate family')
        ids.add(cid); families.add(fam)
        require(c.get('split')==role and c.get('category') in CATEGORIES,'Wrong role/category')
        p=c.get('provenance',{})
        require(all(p.get(k) for k in ['author_or_generator','method','origin_id','semantic_family_id','authored_sha256']),'Missing generated provenance')
        require(p['method']=='session_authored_dialogue_literals' and p.get('actual_call') is False and
                p.get('third_party_transcript') is False and not test_origin(p['origin_id']),'Unapproved source origin')
        require(c.get('rights_basis')=='user_authorized_self_authored_internal_synthetic_research','Source use basis invalid')
        us=c.get('utterances',[])
        require(len(us)==8,'Eight new utterances per family required')
        for i,u in enumerate(us,1):
            require(type(u.get('utterance_id')) is int and u['utterance_id']==i,'Utterance IDs out of order/duplicated')
            require(u.get('speaker') in ('speaker_A','speaker_B'),'Speaker invalid')
            text=u.get('text')
            require(isinstance(text,str) and text.strip() and 'history_texts' not in u,'Current text required; history is computed')
            require(not re.search(r'(?:\d[ -]?){7,}|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|https?://',text),'Unmasked contact/identifier/link')
            require(all(t in MASKS for t in re.findall(r'\[([A-Z_]+)\]',text)),'Unknown mask')
            ls=u.get('labels')
            require(isinstance(ls,list) and all(l in LABELS for l in ls) and ls==sorted(set(ls),key=LABELS.index),'Label order/duplicates invalid')
            require(type(u.get('is_phishing')) is bool and u['is_phishing']==bool(ls),'Risk/type mismatch')
        key=normalized(' '.join(u['text'] for u in us))
        require(key not in texts,'Duplicate whole dialogue'); texts.add(key)
    return statistics(conversations)


def load_research_split(role, manifest_path):
    allowed_role(role)
    path=inside(manifest_path,DATA)
    require(path.name=='research_manifest.json','Separate research manifest required')
    m=read_json(path)
    require(m.get('schema')=='research-synthetic-v3/1' and all(m.get(k)==v for k,v in POLICY_FIELDS.items()),'Not a synthetic research manifest')
    require(m.get('label_order')==list(LABELS) and m.get('mode')=='research_synthetic_v3','Wrong research mode/labels')
    require(m.get('authorization',{}).get('scope')=='explicit_user_internal_synthetic_generation_and_training' and
            re.fullmatch('[0-9a-f]{64}',m['authorization'].get('request_sha256','')),'Explicit research authorization missing')
    require(set(m['splits'])=={'train','validation'},'No TEST role permitted')
    require(m['splits'][role]['path']=={'train':'train_additions.jsonl','validation':'validation_new.jsonl'}[role],'Unexpected research file')
    target=evidence_file(path.parent,m['splits'][role]); cs=jsonl(target)
    validate_research(cs,role)
    return Partition(role,tuple(cs),sha(target),str(target))


def load_research_inputs(manifest_path):
    train=load_research_split('train',manifest_path); val=load_research_split('validation',manifest_path)
    old=load_legacy('train'); old_val=load_legacy('validation')
    policy_path=V2/'reports/v2_stage4_20261109_v1/data_use_policy.json'
    policy=read_json(policy_path)
    require(policy['purpose']=='internal_experiment' and policy['source_kind']=='llm_synthetic' and
            policy['human_approved'] is False and policy['production_training_authorized'] is False,'Inherited research use basis changed')
    for p,n,norm in [(train,24,12),(val,32,12)]:
        s=statistics(p.conversations)
        require(s['conversations']==n and s['utterances']==n*8 and s['normal_conversations']==norm,'Planned counts not met')
        for l in ['information_probing','personal_information']:
            require(s['types'][l]['positive']>=18 and s['types'][l]['positive_families']>=6,'Focus support not met')
        require(all(s['types'][l]['positive']>0 for l in LABELS) if p.role=='validation' else True,'Validation label missing')
        cats=Counter(c['category'] for c in p.conversations if not any(u['is_phishing'] for u in c['utterances']))
        require(all(cats[k]>=v for k,v in dict(financial=3,official=2,identity=3,app=2,quotation=2).items()),'Normal categories missing')
    # Compare new data with each other and each known v2 development partition.
    # The existing v2 train/validation mutual relationship is not re-optimized.
    check_disjoint(train.conversations,val.conversations)
    for a in [train,val]:
        for b in [old,old_val]: check_disjoint(a.conversations,b.conversations)
    bindings=dict(train=train.data_sha256,validation=val.data_sha256,legacy_train=old.data_sha256,
                  legacy_validation=old_val.data_sha256,inherited_policy_sha256=sha(policy_path),
                  research_manifest_sha256=sha(manifest_path))
    return Partition('train',old.conversations+train.conversations,digest(bindings),str(manifest_path)),val,old_val,bindings
