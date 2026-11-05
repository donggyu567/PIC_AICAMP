"""Prioritize existing concerns and proposed holdout QA; assign no approvals."""
import csv
import json
import sys
from pathlib import Path
from plan_splits import ROOT,INPUT,OUTPUT,load,write,normalize
sys.path.insert(0,str(ROOT/'dataset/scripts'))
from audit_v2_pipeline import compare,utterances

REPORTS=ROOT/'reports/v2_experiment_design'


def csv_write(name,rows,columns):
    with (REPORTS/name).open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=columns);writer.writeheader();writer.writerows(rows)


def main():
    previous=ROOT/'reports/v2_pipeline_audit'
    old=[json.loads(s) for s in (previous/'human_review_cases.jsonl').read_text(encoding='utf-8').splitlines()]
    prioritized=[]
    for row in old:
        text=' '.join(row['categories'])
        priority='P0' if '시나리오' in text or '실제 v1' in text else 'P1'
        if row['categories']==['기존 TRAIN 동일 문장']:priority='P2'
        prioritized.append(dict(priority=priority,id=row['id'],split=row['split'],original_text=row['original_text'],
            original_labels=json.dumps(row['original_labels'],ensure_ascii=False),categories=json.dumps(row['categories'],ensure_ascii=False),
            reason=' '.join(row['reasons']),proposal=' '.join(row['proposals']),duplicate_confirmed=False,status='needs_human_review'))
    prioritized.sort(key=lambda r:(r['priority'],r['split'],r['id']))
    csv_write('prioritized_existing_132.csv',prioritized,list(prioritized[0]))
    plan=json.loads((OUTPUT/'split_review_candidate.json').read_text(encoding='utf-8'))
    labels=load(INPUT/'labels.jsonl');texts=load(INPUT/'tuned.jsonl')
    by_key={(r['conversation_id'],r['utterance_id']):r for r in labels}
    qa=[]
    for r in texts:
        role=plan['conversation_to_split'][r['conversation_id']]
        if role=='train':continue
        label=by_key[r['conversation_id'],r['utterance_id']]
        qa.append(dict(priority='P0',candidate_role=role,id=f"{r['conversation_id']}-{r['utterance_id']}",original_text=r['tuned_text'],
            original_is_phishing=label['is_phishing'],original_labels=json.dumps(label['labels'],ensure_ascii=False),source=label['source'],
            source_path=label['source_path'],historical_status=label['label_status'],
            reason='역사적 학습 사용 승인은 평가 정답 품질 확인과 다름. 대화 전체·현재 위험 행위·마스킹·가이드 일치 여부를 독립 검수.',
            status='needs_human_gold_review_not_approved'))
    csv_write('v1_proposed_holdout_gold_review.csv',qa,list(qa[0]))
    exceptions=json.loads((REPORTS/'short_normal_exceptions_pending.json').read_text(encoding='utf-8'))['edges']
    exception_rows=[dict(priority='P0',edge=i,left=e['left'],right=e['right'],left_role=plan['conversation_to_split'][e['left']],right_role=plan['conversation_to_split'][e['right']],
        kind=e['kind'],detail=json.dumps(e['detail'],ensure_ascii=False),
        proposal='짧은 정상 공통 표현인지 또는 같은 시나리오 증거인지 사람이 판단. 예외 불인정이면 해당 그룹을 합치고 모든 후보 분할·설정을 재생성; 결과로 성능을 골라서는 안 됨.',
        duplicate_scenario_confirmed=False,status='exception_not_approved') for i,e in enumerate(exceptions,1)]
    csv_write('short_normal_exception_review.csv',exception_rows,list(exception_rows[0]))
    synthetic=load(ROOT/'dataset/04. processed/v2_train_expansion/train_24_mixed_review_candidate.jsonl')
    original=[dict(id=f"{r['conversation_id']}-{r['utterance_id']}",text=r['tuned_text'],normalized=normalize(r['tuned_text'])) for r in texts if plan['conversation_to_split'][r['conversation_id']]!='train']
    result=compare(utterances(synthetic),original)
    write(REPORTS/'synthetic_vs_proposed_holdouts.json',dict(status='LEXICAL_SCREEN_ONLY_SEMANTIC_REVIEW_PENDING',**result,
        current_approved_synthetic=0,synthetic_TEST_created=False))
    overlap=json.loads((previous/'independence_result.json').read_text(encoding='utf-8'))['v2_train_vs_actual_v1']['candidates']
    mapped=[]
    for row in overlap:
        cid,uid=row['right'].rsplit('-',1)
        mapped.append(dict(row,v1_candidate_split=plan['conversation_to_split'][cid],priority='P0_INVESTIGATE_NOT_CONFIRMED_LEAKAGE',
            note='현재 분할 후보에서는 v1 원문이 TRAIN에 있음. 문장 유사성은 확정된 시나리오 중복이 아니며 의미적 검토는 유지.'))
    write(REPORTS/'v1_similarity_candidate_mapping.json',mapped)
    from collections import Counter
    summary=dict(existing_utterance_cases=132,priority_counts=dict(Counter(r['priority'] for r in prioritized)),
        existing_semantic_scenario_pairs=9,existing_v1_similar_turn_pairs=len(mapped),
        new_holdout_gold_QA_rows=len(qa),short_normal_cross_split_exception_edges=len(exceptions),
        approved_synthetic=0,existing_sources_unchanged=True,approvals_assigned=False,
        note='Different files overlap in subjects; counts are tasks/edges, not distinct independent data points.')
    write(REPORTS/'review_priority_summary.json',summary)
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
