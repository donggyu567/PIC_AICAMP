"""Approval denial, single-use claims, portable inference errors and family uncertainty.

Approval fixtures exist only in memory and never create a real release record.
No TEST ciphertext/body/gold or actual model training is used by these tests.
"""
from datetime import datetime,timezone,timedelta
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'experiments/koelectra_v2'))
from expanded_common import GateError,LABELS
from stage5_runtime import validate_request,serve_request,output_response,relative_file,ResearchPredictor
import stage5_custody as custody


class HandoffTests(unittest.TestCase):
    def approval(self):
        now=datetime(2026,11,10,tzinfo=timezone.utc)
        release=dict(schema='custodian-explicit-test-release/1',approved_action='one_time_fixed_plan_test_evaluation',
            plan_sha256='a'*64,receipt_sha256='b'*64,custodian_sid='UNIT_FIXTURE_SID',approval_reference='IN_MEMORY_UNIT_FIXTURE_NOT_HUMAN',
            approved_at=now.isoformat(),expires_at=(now+timedelta(hours=1)).isoformat(),human_label_review_complete=False,deployment_approved=False)
        return release,dict(plan_sha='a'*64,receipt_sha='b'*64,custodian_sid='UNIT_FIXTURE_SID',now=now)

    def test_no_approval_denies_before_any_test_io(self):
        with patch('stage5_custody.read') as reader,patch('stage5_custody.decrypt') as decryptor:
            with self.assertRaises(GateError):custody.evaluate(Path('unused-plan.json'),None)
        reader.assert_not_called();decryptor.assert_not_called()

    def test_release_issue_requires_separate_explicit_ack_before_io(self):
        with patch('stage5_custody.read') as reader:
            with self.assertRaises(GateError):custody.issue_release(Path('unused'),'not an approval',False)
        reader.assert_not_called()

    def test_wrong_custodian_denied(self):
        r,args=self.approval();args['custodian_sid']='OTHER'
        with self.assertRaises(GateError):custody.validate_approval(r,**args)

    def test_changed_plan_or_receipt_denied(self):
        for key in ['plan_sha','receipt_sha']:
            r,args=self.approval();args[key]='c'*64
            with self.assertRaises(GateError):custody.validate_approval(r,**args)

    def test_expired_or_future_approval_denied(self):
        for delta in [-1,2]:
            r,args=self.approval();args['now']+=timedelta(hours=delta)
            with self.assertRaises(GateError):custody.validate_approval(r,**args)

    def test_access_release_cannot_assert_label_or_deployment_approval(self):
        for key in ['human_label_review_complete','deployment_approved']:
            r,args=self.approval();r[key]=True
            with self.assertRaises(GateError):custody.validate_approval(r,**args)

    def test_one_claim_across_seeds_models_and_plans(self):
        with tempfile.TemporaryDirectory() as folder:
            first=custody.reserve_once(folder,'a'*64,'b'*64)
            before=first.read_bytes()
            with self.assertRaises(FileExistsError):custody.reserve_once(folder,'c'*64,'d'*64)
            self.assertEqual(before,first.read_bytes())

    def test_invalid_requests(self):
        for request in [None,{},dict(current_text=' '),dict(current_text='x',history_texts='past'),dict(current_text='x',future_text='future')]:
            with self.assertRaises(ValueError):validate_request(request)

    def test_normal_success_is_not_an_error(self):
        result=output_response([-2.]*9,[.5]*9,seed=42,model_sha='a'*64)
        self.assertTrue(result['ok']);self.assertFalse(result['result']['is_phishing'])
        self.assertEqual(result['result']['detected_types'],[]);self.assertIsNone(result['error'])

    def test_heads_remain_independent_and_ordered(self):
        result=output_response([-2.,2.]+[-2.]*7,[.5]*9,seed=42,model_sha='a'*64)['result']
        self.assertFalse(result['is_phishing']);self.assertEqual(result['detected_types'],[LABELS[0]])
        self.assertEqual(list(result['type_probabilities']),list(LABELS))

    def test_nonfinite_output_is_rejected(self):
        with self.assertRaises(ValueError):output_response([float('nan')]*9,[.5]*9,seed=42,model_sha='a'*64)

    def test_model_failure_is_never_reported_as_normal(self):
        class Broken:
            def predict(self,request):raise ValueError('internal model failure')
        result=serve_request(Broken(),dict(current_text='valid'))
        self.assertFalse(result['ok']);self.assertIsNone(result['result'])
        self.assertEqual((result['http_status'],result['error']['code']),(500,'MODEL_INFERENCE_ERROR'))

    def test_client_error_and_not_ready_distinct(self):
        class Unused:
            def predict(self,request):raise AssertionError('invalid request must not reach model')
        self.assertEqual(serve_request(Unused(),dict(current_text=''))['error']['code'],'INVALID_REQUEST')
        self.assertEqual(serve_request(None,dict(current_text='valid'))['error']['code'],'NOT_READY')

    def test_overlong_error_distinct(self):
        from risk_speech_ai.tokenization import InputTooLongError
        class Overlong:
            def predict(self,request):raise InputTooLongError(600,0)
        result=serve_request(Overlong(),dict(current_text='valid'))
        self.assertEqual((result['http_status'],result['error']['code']),(422,'INPUT_TOO_LONG'))

    def test_manifest_trust_anchor_required_before_model_load(self):
        with patch('transformers.AutoTokenizer.from_pretrained') as loader:
            with self.assertRaises(ValueError):ResearchPredictor(Path('unused'),expected_manifest_sha=None)
        loader.assert_not_called()

    def test_bundle_reference_cannot_escape(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):relative_file(folder,dict(path='../outside.pt',sha256='a'*64))

    def test_family_bootstrap_is_paired_deterministic_and_skips_missing_support(self):
        rows=[dict(conversation_id='fixture1',scenario_family_id='fixture1',is_phishing=True,labels=[LABELS[0]]),
              dict(conversation_id='fixture2',scenario_family_id='fixture2',is_phishing=False,labels=[])]
        good=[[8.,8.]+[-8.]*7,[-8.]*9];bad=[[-8.]*9,[-8.]*9]
        logits={'B_ratio':{42:good,43:good,44:good},'A_epoch':{42:bad,43:bad,44:bad}}
        a=custody.family_bootstrap(rows,logits,[.5]*9,repetitions=30,seed=123)
        b=custody.family_bootstrap(rows,logits,[.5]*9,repetitions=30,seed=123)
        self.assertEqual(a,b)
        self.assertEqual(a['paired_binary_f1_delta_B_minus_comparator']['A_epoch']['ci95'],[1.,1.])
        self.assertEqual(a['by_arm']['B_ratio'][LABELS[-1]]['valid_repetitions'],0)
        self.assertLess(a['by_arm']['B_ratio']['risk']['valid_repetitions'],30)


if __name__=='__main__':unittest.main()
