from copy import deepcopy
import unittest
from unittest.mock import patch
from v3_lite.src.common import DATA,GateError
from v3_lite.src.data import load_manifest
from v3_lite.src.research_data import load_research_inputs,load_research_split,test_origin,validate_research


class ResearchData(unittest.TestCase):
    def test_explicit_research_route_and_counts(self):
        manifest=DATA/'research_synthetic_20261117_v1/research_manifest.json'
        if not manifest.exists():
            self.skipTest('Private research corpus intentionally excluded from public Git')
        train,val,old,bindings=load_research_inputs(manifest)
        self.assertEqual(len(train.samples()),848); self.assertEqual(len(val.samples()),256)
        self.assertEqual(len(old.samples()),256)
        self.assertFalse(val.conversations[0]['human_reviewed'])
        self.assertEqual(len({c['family_id'] for c in val.conversations}),32)
        with self.assertRaises(GateError): load_manifest(manifest)

    def test_test_role_refused_before_read(self):
        with patch('v3_lite.src.research_data.read_json') as read:
            with self.assertRaises(GateError): load_research_split('test','no-file')
            read.assert_not_called()

    def test_research_never_claims_human_or_production_approval(self):
        manifest=DATA/'research_synthetic_20261117_v1/research_manifest.json'
        if not manifest.exists(): self.skipTest('Private research corpus excluded')
        c=deepcopy(load_research_split('train',manifest).conversations[0])
        for field in ['human_reviewed','human_review_complete','approved_for_production','deployment_allowed']:
            bad=deepcopy(c); bad[field]=True
            with self.assertRaises(GateError): validate_research([bad],'train')
        c['provenance']['third_party_transcript']=True
        with self.assertRaises(GateError): validate_research([c],'train')

    def test_exact_test_origin_token_not_contest_word(self):
        self.assertFalse(test_origin('V3-VALIDATION-contest-nondisclosure'))
        self.assertTrue(test_origin('SYN3-TEST-0001'))
