"""Non-sensitive unit fixtures. Never a reviewed research corpus."""
from copy import deepcopy
from v3_lite.src.common import LABELS
from v3_lite.src.data import utterance_binding


def conversation(cid='V3-FIXTURE-TRAIN-001',family='fixture-phone-inquiry',role='train'):
    texts=['이 통화에서 어떤 점을 확인하려는 건가요?', '사용 중인 통신사만 확인할게요.',
           '그 질문의 목적을 먼저 설명해 주세요.', '설명 없이 답변을 요구해서는 곤란합니다.',
           '방금 도착한 인증번호를 읽어 주세요.', '인증번호는 전달하지 않겠습니다.',
           '제가 직접 문의 경로를 찾아보겠습니다.', '안내 내용을 확인하고 통화를 마칠게요.']
    us=[]
    for i,text in enumerate(texts,1):
        labels=['information_probing'] if i==2 else ['personal_information'] if i==5 else []
        us.append(dict(utterance_id=i,speaker='speaker_A' if i%2 else 'speaker_B',text=text,
                       is_phishing=bool(labels),labels=labels,masking_reviewed=True))
    return dict(conversation_id=cid,family_id=family,split=role,source='automated_unit_test_fixture',
                category='identity',review_status='reviewed',
                provenance=dict(method='unit_fixture',author_or_generator='automated_test',created_at='2026-11-17T00:00:00+09:00',
                    origin_id=cid,semantic_family_id=family),
                rights=dict(status='documented',permitted_uses=[role],evidence={'path':'fixture_rights.json','sha256':'0'*64}),utterances=us)


def simulated_reviews(cs):
    """Returned objects only exist in test memory; no approval records are persisted."""
    return [dict(record_type='human_review',status='resolved',conversation_id=c['conversation_id'],
                 utterance_id=u['utterance_id'],content_sha256=utterance_binding(c,u),
                 reviewers=[dict(reviewer_id=f'SIMULATED_TEST_RATER_{i}',human=True,independent=True,
                     reviewed_at='2026-11-17T00:00:00+09:00',is_phishing=u['is_phishing'],labels=deepcopy(u['labels'])) for i in [1,2]])
            for c in cs for u in c['utterances']]


def metrics(f1=.5,ap=.5,normal_fp=1):
    return dict(binary=dict(recall=.9,f1=.9),per_type={l:dict(f1=f1,recall=.8,average_precision=ap) for l in LABELS},
                conversations=dict(normal=12,normal_false_alerts=normal_fp))
