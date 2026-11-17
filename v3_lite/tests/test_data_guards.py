from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from v3_lite.src.common import DATA, LABELS, GateError
from v3_lite.src.data import (Partition,check_disjoint,evidence_file,load_manifest,load_split,
                             load_training_inputs,validate_reviews,validate_rights,validate_schema)
from v3_lite.src.train import run_lite
from v3_lite.tests.fixtures import conversation,simulated_reviews


class DataGuards(unittest.TestCase):
    def test_schema_and_risk_type_contract(self):
        c=conversation(); self.assertEqual(validate_schema([c],'train')['utterances'],8)
        c['utterances'][1]['is_phishing']=False
        with self.assertRaises(GateError): validate_schema([c],'train')

    def test_label_order_duplicate_ids_and_unknowns(self):
        mutations=[lambda c:c['utterances'][0].update(labels=['unknown'],is_phishing=True),
                   lambda c:c['utterances'][1].update(utterance_id=1),
                   lambda c:c['utterances'][0].update(labels=[LABELS[2],LABELS[0]],is_phishing=True)]
        for fn in mutations:
            c=conversation(); fn(c)
            with self.assertRaises(GateError): validate_schema([c],'train')
        with self.assertRaises(GateError): validate_schema([conversation(),conversation()],'train')

    def test_test_role_denied_before_any_io(self):
        with patch('v3_lite.src.data.load_manifest') as reader:
            for role in ['test','TEST','production','../test']:
                with self.assertRaises(GateError): load_split(role,'arbitrary/sealed/path')
            reader.assert_not_called()

    def test_test_and_traversal_paths_denied_before_content_read(self):
        for name in ['test.json','../train_additions.jsonl','C:/outside.json','..\\outside.json','/outside.json']:
            with self.assertRaises(GateError): evidence_file(DATA,{'path':name,'sha256':'0'*64})

    def test_rights_masking_and_history_rejected(self):
        mutations=[lambda c:c.update(rights={}),lambda c:c['utterances'][0].update(text='전화 010-1234-5678'),
                   lambda c:c['utterances'][0].update(text='a@example.com'),
                   lambda c:c['utterances'][0].update(masking_reviewed=False),
                   lambda c:c['utterances'][0].update(history=['future']),
                   lambda c:c['provenance'].update(origin_id='SYN3-TEST-0001')]
        for fn in mutations:
            c=conversation(); fn(c)
            with self.assertRaises(GateError): validate_schema([c],'train')

    def test_rights_evidence_requires_source_scope_and_authority(self):
        c=conversation()
        record=dict(record_type='data_use_authorization',status='confirmed',source_ids=[c['source']],
                    permitted_uses=['train'],authorized_by='SIMULATED_TEST_AUTHORITY',authorized_at='2026-11-17T00:00:00+09:00',basis='unit fixture only')
        validate_rights(c,record,'train')
        for key,value in [('permitted_uses',['validation']),('source_ids',[]),('authorized_by',''),('status','pending')]:
            bad=deepcopy(record); bad[key]=value
            with self.assertRaises(GateError): validate_rights(c,bad,'train')

    def test_review_bindings_two_people_and_resolution(self):
        cs=[conversation()]; rs=simulated_reviews(cs)
        validate_reviews(cs,rs)
        one=deepcopy(rs); one[0]['reviewers']=one[0]['reviewers'][:1]
        with self.assertRaises(GateError): validate_reviews(cs,one)
        same=deepcopy(rs); same[0]['reviewers'][1]['reviewer_id']=same[0]['reviewers'][0]['reviewer_id']
        with self.assertRaises(GateError): validate_reviews(cs,same)
        disagree=deepcopy(rs); disagree[1]['reviewers'][0].update(is_phishing=False,labels=[])
        with self.assertRaises(GateError): validate_reviews(cs,disagree)
        disagree[1]['resolution']=dict(adjudicator_id='SIMULATED_TEST_ADJUDICATOR',reason='fixture resolution branch',
            resolved_at='2026-11-17T00:00:00+09:00',is_phishing=True,labels=['information_probing'])
        validate_reviews(cs,disagree)
        stale=deepcopy(cs); stale[0]['utterances'][0]['text']='변경된 현재 발화'
        with self.assertRaises(GateError): validate_reviews(stale,rs)
        for status in ['pending','automatically_validated']:
            bad=deepcopy(rs); bad[0]['status']=status
            with self.assertRaises(GateError): validate_reviews(cs,bad)

    def test_family_and_near_duplicate_split(self):
        a=conversation(); b=conversation('V3-FIXTURE-VAL-001','fixture-distinct','validation')
        # Different IDs but the same text are rejected.
        with self.assertRaises(GateError): check_disjoint([a],[b])
        b['family_id']=a['family_id']
        with self.assertRaises(GateError): check_disjoint([a],[b])
        b['family_id']='different'; b['provenance']['semantic_family_id']=a['provenance']['semantic_family_id']
        with self.assertRaises(GateError): check_disjoint([a],[b])

    def test_causal_history_uses_only_past_five_turns(self):
        c=conversation(); p=Partition('train',(c,),'fixture','fixture')
        samples=p.samples()
        for i,s in enumerate(samples):
            self.assertEqual(s.history_texts,[u['text'] for u in c['utterances'][max(0,i-5):i]])
            self.assertEqual(s.current_text,c['utterances'][i]['text'])

    def test_fixture_manifest_cannot_authorize_training(self):
        DATA.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='fixture_',dir=DATA) as tmp:
            p=Path(tmp)/'manifest.json'
            p.write_text(json.dumps(dict(schema='v3-lite-data/1',purpose='internal_experiment',artifact_kind='unit_test_fixture')),encoding='utf-8')
            with self.assertRaises(GateError): load_manifest(p)
            with patch('v3_lite.src.train.load_v2_start') as loader:
                with self.assertRaises(GateError): run_lite(p,run_id='fixture-blocked',regression_receipt='absent')
                loader.assert_not_called()

    def test_unapproved_formal_training_and_missing_data_block_before_model(self):
        with patch('v3_lite.src.train.load_v2_start') as loader:
            with self.assertRaises(GateError): run_lite('absent',run_id='fixture-blocked',regression_receipt='absent',purpose='production')
            with self.assertRaises((GateError,FileNotFoundError)): run_lite(DATA/'absent/manifest.json',run_id='fixture-blocked',regression_receipt='absent')
            loader.assert_not_called()
