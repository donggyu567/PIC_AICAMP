"""Configuration/split/path/loss tests; never train a model or approve a label."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'experiments/koelectra_v2'))
import experiment_runtime as run
import plan_splits as split


class ExperimentDesignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config={a:run.read(run.HERE/'configs'/f'{a}.json') for a in ('A','B','C')}
        cls.plan=run.read(run.HERE/'split_review_candidate.json')
        cls.labels=split.load(split.INPUT/'labels.jsonl')
        cls.ids={r['conversation_id'] for r in cls.labels}

    def test_all_configs_and_hashes_valid(self):
        for cfg in self.config.values():run.validate_config(cfg)

    def test_ABC_identical_common_partition_and_conditions(self):
        for field in ('model','input','training','evaluation'):
            self.assertEqual(self.config['A'][field],self.config['B'][field])
            self.assertEqual(self.config['B'][field],self.config['C'][field])
        for cfg in self.config.values():self.assertEqual(cfg['data']['split_sha256'],self.config['A']['data']['split_sha256'])

    def test_A_unweighted_BC_same_frozen_training_weights(self):
        self.assertIsNone(self.config['A']['loss']['type_pos_weight'])
        self.assertEqual(self.config['B']['loss'],self.config['C']['loss'])
        p=run.read(ROOT/self.config['B']['loss']['type_pos_weight']['manifest'])
        self.assertEqual(p['train_utterances'],self.plan['distribution']['train']['utterances'])
        expected=[sum(l in r['labels'] for r in self.labels if self.plan['conversation_to_split'][r['conversation_id']]=='train') for l in split.LABELS]
        self.assertEqual(p['positives'],expected)

    def test_C_fails_closed_without_approved_synthetic(self):
        with self.assertRaises(run.ExperimentError):run.samples_for(self.config['C'],'train')

    def test_A_and_B_same_actual_samples(self):
        self.assertEqual(run.samples_for(self.config['A'],'train'),run.samples_for(self.config['B'],'train'))

    def test_partition_disjoint_complete(self):
        buckets=[{c for c,s in self.plan['conversation_to_split'].items() if s==role} for role in ('train','validation','test')]
        self.assertEqual(set.union(*buckets),self.ids)
        self.assertTrue(all(not a&b for i,a in enumerate(buckets) for b in buckets[i+1:]))
        run.validate_manifest(self.plan,self.ids)

    def test_group_leakage_rejected(self):
        p=copy.deepcopy(self.plan);group=next(g for g in p['groups'].values() if len(g)>1)
        p['conversation_to_split'][group[0]]='test' if p['conversation_to_split'][group[1]]!='test' else 'train'
        with self.assertRaises(run.ExperimentError):run.validate_manifest(p,self.ids)

    def test_missing_conversation_rejected(self):
        p=copy.deepcopy(self.plan);p['conversation_to_split'].pop(next(iter(self.ids)))
        with self.assertRaises(run.ExperimentError):run.validate_manifest(p,self.ids)

    def test_same_seed_reproduces_candidate_allocation(self):
        a,g=split.assign(self.plan['groups'],self.labels,ratios=(.70,.15,.15),seed=split.SEED)
        self.assertEqual(a,self.plan['conversation_to_split'])
        self.assertEqual((a,g),split.assign(self.plan['groups'],self.labels,ratios=(.70,.15,.15),seed=split.SEED))

    def test_candidate_never_gold_or_authorized(self):
        self.assertFalse(self.plan['training_authorized'])
        self.assertFalse(self.plan['evaluation_labels_human_verified'])
        self.assertFalse(self.plan['short_turn_exception_policy_human_approved'])

    def test_both_holdouts_have_legitimate_calls_and_phishing(self):
        for role in ('validation','test'):
            self.assertGreater(self.plan['distribution'][role]['entirely_normal_conversations'],0)
            self.assertGreater(self.plan['distribution'][role]['phishing'],0)

    def test_rare_app_source_stays_train_single_group(self):
        ids={r['conversation_id'] for r in self.labels if 'app_installation' in r['labels']}
        self.assertEqual({self.plan['conversation_to_split'][c] for c in ids},{'train'})
        self.assertEqual(len(self.plan['rare_label_feasibility']['app_installation']['independent_components']),1)

    def test_output_paths_distinct_by_arm_seed_run(self):
        paths={run.output_path(cfg,s,f'test-{s}') for cfg in self.config.values() for s in cfg['training']['seeds']}
        self.assertEqual(len(paths),9)

    def test_path_traversal_rejected(self):
        with self.assertRaises(run.ExperimentError):run.output_path(self.config['A'],42,'../escape')

    def test_v1_checkpoint_root_rejected(self):
        cfg=copy.deepcopy(self.config['A']);cfg['output']['root']='artifacts/risk_speech_ai'
        with self.assertRaises(run.ExperimentError):run.output_path(cfg,42,'test')

    def test_unregistered_seed_rejected(self):
        with self.assertRaises(run.ExperimentError):run.output_path(self.config['A'],99,'test')

    def test_existing_run_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(run,'ROOT',Path(directory)):
            path=run.reserve_output(self.config['A'],42,'isolated')
            sentinel=path/'human-log.txt';sentinel.write_text('keep',encoding='utf-8')
            with self.assertRaises(run.ExperimentError):run.reserve_output(self.config['A'],42,'isolated')
            self.assertEqual(sentinel.read_text(),'keep')

    def test_wrong_input_hash_rejected(self):
        cfg=copy.deepcopy(self.config['A']);cfg['data']['labels_sha256']='0'*64
        with self.assertRaises(run.ExperimentError):run.validate_config(cfg)

    def test_training_flag_rejected(self):
        cfg=copy.deepcopy(self.config['A']);cfg['execution']['training_enabled']=True
        with self.assertRaises(run.ExperimentError):run.validate_config(cfg)

    def test_changed_threshold_or_revision_rejected(self):
        for field in ('threshold','revision'):
            cfg=copy.deepcopy(self.config['A'])
            if field=='threshold':cfg['evaluation']['risk_threshold']=.3
            else:cfg['model']['revision']='main'
            with self.assertRaises(run.ExperimentError):run.validate_config(cfg)

    def test_weighted_loss_no_backward_or_model_training(self):
        import torch
        from risk_speech_ai.model import ModelOutput
        output=ModelOutput(torch.zeros((1,1),requires_grad=True),torch.zeros((1,8),requires_grad=True))
        y=torch.ones((1,1));types=torch.ones((1,8))
        a=run.loss_values(output,y,types,self.config['A'])
        b=run.loss_values(output,y,types,self.config['B'])
        c=run.loss_values(output,y,types,self.config['C'])
        self.assertGreater(b[0].item(),a[0].item())
        self.assertEqual(b[0].item(),c[0].item())
        self.assertEqual(a[1].item(),b[1].item())
        self.assertIsNone(output.risk_logits.grad)
        self.assertIsNone(output.type_logits.grad)

    def test_missing_positive_not_reported_as_full8_success(self):
        from risk_speech_ai.metrics import multilabel_metrics
        m=multilabel_metrics([[0]*8,[0]*8],[[.1]*8,[.1]*8])
        self.assertIsNone(m['macro']['f1'])
        self.assertEqual(m['macro']['defined_f1_labels'],0)


if __name__=='__main__':unittest.main()
