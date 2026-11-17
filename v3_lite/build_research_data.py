"""Serialize individually authored literals; no repetitive text generation."""
from datetime import datetime,timezone
import hashlib
from pathlib import Path
from .src.common import DATA,LABELS,create_json,digest,read_json,require,sha
from .src.research_data import POLICY_FIELDS,load_research_inputs,validate_research

OUT=DATA/'research_synthetic_20261117_v1'
CODES=dict(zip('IMPASTLF',LABELS))


def parse(role):
    authored=OUT/f'{role}_authored.txt'
    plan=read_json(OUT/'split_plan.json')[role]
    expected={c['family_id']:c for c in plan}
    cs=[]; current=None
    for line in authored.read_text(encoding='utf-8-sig').splitlines():
        if not line.strip(): continue
        if line.startswith('@ '):
            family=line[2:]; require(family in expected,'Unknown prospective family')
            item=expected[family]
            current=dict(conversation_id=f'V3-{role.upper()}-{len(cs)+1:04d}',family_id=f'V3-{role.upper()}-{family}',
                split=role,source='PROJECT_CODEX_SYNTHETIC_V3',category=item['category'],primary_type=None if item['primary']=='N' else CODES[item['primary']],
                **POLICY_FIELDS,review_status='ai_provisional',label_status='provisional',
                rights_basis='user_authorized_self_authored_internal_synthetic_research',
                provenance=dict(method='session_authored_dialogue_literals',author_or_generator='Codex session; exact backend model ID not asserted',
                    origin_id=f'V3-{role.upper()}-{family}',semantic_family_id=family,actual_call=False,third_party_transcript=False,
                    authored_sha256=sha(authored)),utterances=[])
            cs.append(current)
        else:
            speaker,codes,text=line.split('|',2)
            ls=[] if codes=='-' else sorted([CODES[c] for c in codes],key=LABELS.index)
            current['utterances'].append(dict(utterance_id=len(current['utterances'])+1,speaker='speaker_'+speaker,
                text=text,is_phishing=bool(ls),labels=ls,label_status='provisional',human_reviewed=False))
    require(len(cs)==len(plan),'Prospective scenario count mismatch')
    validate_research(cs,role)
    return cs


if __name__=='__main__':
    import json
    import argparse
    import re
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--authorization-sha',required=True,help='SHA-256 of the actual explicit user research authorization; not a human-review record')
    args=parser.parse_args()
    require(re.fullmatch('[0-9a-f]{64}',args.authorization_sha),'Authorization SHA-256 required')
    splits={}
    for role,name in [('train','train_additions.jsonl'),('validation','validation_new.jsonl')]:
        cs=parse(role)
        content=''.join(json.dumps(c,ensure_ascii=False,separators=(',',':'))+'\n' for c in cs)
        if (OUT/name).exists():
            require((OUT/name).read_text(encoding='utf-8')==content,'Existing authored data differs; use new version')
        else:
            with (OUT/name).open('x',encoding='utf-8') as f: f.write(content)
        splits[role]=dict(path=name,sha256=sha(OUT/name))
    create_json(OUT/'research_manifest.json',dict(schema='research-synthetic-v3/1',mode='research_synthetic_v3',**POLICY_FIELDS,
        label_order=list(LABELS),authorization=dict(scope='explicit_user_internal_synthetic_generation_and_training',request_sha256=args.authorization_sha),
        splits=splits,prospective_split_plan_sha256=sha(OUT/'split_plan.json'),
        label_status='provisional',third_party_material_used=False,test_body_accessed=False))
    tr,val,old,bindings=load_research_inputs(OUT/'research_manifest.json')
    from .src.data import statistics
    create_json(OUT/'quality_before_model_scores.json',dict(status='PASS',bindings=bindings,
        final_train=statistics(tr.conversations),new_validation=statistics(val.conversations),
        automated_schema_and_lexical_checks=True,ai_semantic_review_complete=True,human_review_complete=False,
        semantic_review='Session separately reread scenarios/labels; focus acts/context versus legitimate minimum information requests checked. Not independent human review; semantic independence remains unproven.',
        external_test_comparison=False))
    print('DATA PASS',len(tr.conversations),sum(len(c['utterances']) for c in tr.conversations),len(val.conversations))
