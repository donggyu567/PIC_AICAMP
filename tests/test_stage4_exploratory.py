"""No optimizer updates: exploratory-mode isolation and registered actual-data inputs."""
import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'experiments/koelectra_v2'))
from expanded_common import GateError, LABELS
from expanded_data import load_partition
from stage3_data import BASE, jsonl
import stage4_exploratory as s


class ExploratoryTests(unittest.TestCase):
    @unittest.skipUnless((BASE/'data_use_manifest.json').is_file(), 'Internal research manifest intentionally not published')
    def test_precheck_real_completed_stage3_without_test_read(self):
        train,val,convs,bindings=s.precheck()
        self.assertEqual((len(train.samples),len(val.samples)),(656,256))
        self.assertEqual((len(convs['train']),len(convs['validation'])),(80,32))
        self.assertTrue(all(len(v)==64 for v in bindings.values()))

    def test_policy_never_asserts_human_or_production_approval(self):
        for k in ['human_review_complete','human_approved','deployment_approved','production_training_authorized']:
            self.assertIs(s.POLICY[k],False)
        self.assertEqual(s.POLICY['mode'],'exploratory_training')

    def test_approved_augmentation_and_matched_budget_remain_blocked(self):
        for arm in ['C_approved','B_step_matched']:
            self.assertEqual(s.blocked_arms()[arm]['status'],'BLOCKED')
            with self.assertRaises(GateError): s.research_config(arm,42)

    def test_unknown_seed_and_arm_rejected(self):
        for arm,seed in [('A_epoch',99),('TEST',42)]:
            with self.assertRaises(GateError): s.research_config(arm,seed)

    def test_research_retains_registered_hyperparameters_and_initialization(self):
        for arm in ['A_epoch','B_ratio']:
            cfg=s.research_config(arm,42)['stage2_runtime']
            self.assertEqual((cfg['epochs'],cfg['batch_size'],cfg['learning_rate'],cfg['weight_decay']),(3,8,2e-5,.01))
            self.assertEqual(cfg['thresholds'],[.5]*9)
            self.assertEqual(cfg['initialization'],'fresh_pinned_public_encoder_and_seeded_heads')

    def test_weights_use_only_supplied_train_rows_and_canonical_order(self):
        rows=[dict(labels=[LABELS[0]])]+[dict(labels=[]) for _ in range(4)]
        self.assertEqual(s.weights_from_rows(rows),[4.]+[1.]*7)
        self.assertEqual(s.weights_from_rows(rows*3),[4.]+[1.]*7)
        self.assertEqual(s.weights_from_rows(rows+[dict(labels=[]) for _ in range(20)])[0],10.)

    @unittest.skipUnless((BASE/'data_use_manifest.json').is_file(), 'Internal research manifest intentionally not published')
    def test_flatten_preserves_current_labels_and_true_whole_normal_flags(self):
        cs=jsonl(BASE/'validation_32_synthetic.jsonl')
        rows=s.flatten(cs)
        self.assertEqual(len(rows),256)
        self.assertEqual(sum(r['hard_negative'] for r in rows),64)
        self.assertEqual(sum(r['is_phishing'] for r in rows),72)

    @unittest.skipUnless((BASE/'data_use_manifest.json').is_file(), 'Internal research manifest intentionally not published')
    def test_research_manifest_still_rejected_by_original_gate(self):
        with self.assertRaises(GateError): load_partition(BASE,BASE/'data_use_manifest.json','train')

    def test_prediction_role_and_identity_denied_before_checkpoint_read(self):
        p=dict(schema='exploratory-predictions/1',role='test',arm='A_epoch',seed=42,epoch=1,bindings={},row_keys=[])
        with patch('stage4_exploratory.sha') as hasher:
            with self.assertRaises(GateError): s.validate_prediction(p,42,1,'A_epoch',{},[])
        hasher.assert_not_called()

    def test_undefined_metrics_are_not_invented_as_zero(self):
        self.assertIsNone(s.mean_defined([None,None,None]))
        self.assertEqual(s.mean_defined([None,.2,.4]),.30000000000000004)


if __name__=='__main__':unittest.main()
