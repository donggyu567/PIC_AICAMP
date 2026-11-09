"""Behavioral tests using temporary evidence, tiny Electra and inert token fixtures."""
from __future__ import annotations

import copy
from dataclasses import replace
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import warnings

from expanded_fixtures import make_fixture, tiny_model, predictions, reference, ROOT
from expanded_common import (GateError, LABELS, SEEDS, PROTOCOL, compile_runtime, validate_runtime,
                             sha, digest, read, write_json, publish)
from expanded_data import load_partition, validate_split, check_disjoint, load_receipt
from expanded_checkpoint import RunStore, load_v2, validate_extended, model_for_inference
from expanded_training import train, positive_weights, losses, step_budget
from expanded_evaluation import (probabilities, evaluate_logits, infer_partition, paired_bootstrap,
                                 seed_summary, validate_predictions)
from expanded_selection import select_epoch, select_thresholds, freeze_b, save_selection, validate_frozen
from risk_speech_ai.model import ModelOutput

import numpy as np
import torch


class ExpandedPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(2)
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        cls.parts = make_fixture(cls.root)
        os.environ.update(HF_HUB_CACHE=str(ROOT.parents[1] / '.venv-ai/hf-cache/hub'),
                          HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
        from expanded_assets import load_tokenizer
        cls.tokenizer = load_tokenizer()
        cls.runs = {}
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', RuntimeWarning)
            for seed in SEEDS:
                cls.runs[seed] = train(compile_runtime('B_ratio', seed), cls.parts['train'], cls.parts['validation'],
                    cls.tokenizer, run_id='fixture-B', receipt=cls.parts['receipt'], store_root=cls.root/'runs',
                    fixture_model_factory=tiny_model)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_runtime_is_separate_from_design(self):
        with self.assertRaises(GateError):
            validate_runtime(read(PROTOCOL))
        for arm, epochs in [('A0', 1), ('A_epoch', 3), ('B_ratio', 3), ('B_sqrt5_legacy', 3)]:
            cfg = compile_runtime(arm, 42)
            self.assertEqual(cfg['epochs'], epochs)
            validate_runtime(cfg)

    def test_runtime_hyperparameter_tamper_rejected(self):
        cfg = compile_runtime('A0', 42)
        cfg['learning_rate'] = .1
        with self.assertRaises(GateError):
            validate_runtime(cfg)

    def test_b_threshold_is_not_an_extra_training_arm(self):
        with self.assertRaises(GateError):
            compile_runtime('B_threshold', 42)

    def test_c_requires_actual_b_selection(self):
        with self.assertRaises(GateError):
            compile_runtime('C_approved', 42)

    def test_weights_train_only_cap10_and_zero_positive(self):
        with warnings.catch_warnings(record=True) as caught:
            weight = positive_weights(self.parts['train'])
        self.assertEqual(weight['values'][0], 10.)
        self.assertEqual(weight['values'][1], 3.)
        self.assertEqual(weight['values'][3], 10.)
        self.assertIn('secrecy', weight['unsupported'])
        self.assertTrue(caught)
        with self.assertRaises(GateError):
            positive_weights(self.parts['validation'])
        with self.assertRaises(GateError):
            positive_weights(self.parts['train'], label_order=list(reversed(LABELS)))

    def test_legacy_sqrt5_remains_distinct(self):
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            old = positive_weights(self.parts['train'], policy='sqrt5')['values']
            new = positive_weights(self.parts['train'])['values']
        self.assertNotEqual(old, new)
        self.assertAlmostEqual(old[1], 3.**.5)

    def test_loss_binary_unweighted_and_type_weighted(self):
        output = ModelOutput(torch.zeros((2, 1), requires_grad=True), torch.zeros((2, 8), requires_grad=True))
        risk, labels = torch.ones((2, 1)), torch.ones((2, 8))
        a = losses(output, risk, labels, [1.]*8)
        b = losses(output, risk, labels, [10.]*8)
        self.assertEqual(a[1].item(), b[1].item())
        self.assertGreater(b[2].item(), a[2].item())
        b[0].backward()
        self.assertIsNotNone(output.type_logits.grad)

    def test_nan_inf_and_nonbinary_targets_rejected(self):
        for value in (float('nan'), float('inf')):
            output = ModelOutput(torch.full((1, 1), value), torch.zeros((1, 8)))
            with self.assertRaises(GateError):
                losses(output, torch.zeros((1, 1)), torch.zeros((1, 8)), [1.]*8)
        with self.assertRaises(GateError):
            losses(ModelOutput(torch.zeros((1, 1)), torch.zeros((1, 8))), torch.full((1, 1), .5), torch.zeros((1, 8)), [1.]*8)

    def test_each_epoch_optimizer_snapshot_matches(self):
        result = self.runs[42]
        self.assertEqual([r['epoch'] for r in result['history']], [1, 2, 3])
        self.assertEqual([r['optimizer_steps'] for r in result['history']], [3, 6, 9])
        for index, ref in enumerate(result['references'], 1):
            payload = load_v2(ref['path'], expected_sha256=ref['sha256'], fixture=True)
            self.assertEqual(payload['epoch'], index)
            self.assertEqual(payload['step_count'], index*3)
            self.assertTrue(all(int(s['step']) == index*3 for s in payload['optimizer_state_dict']['state'].values()))

    def test_best_last_are_separate_immutable_snapshots(self):
        result = self.runs[42]
        folder = Path(result['references'][0]['path']).parent
        self.assertTrue((folder/'best.pt').exists() and (folder/'last.pt').exists())
        self.assertEqual(sha(folder/'last.pt'), result['references'][-1]['sha256'])
        self.assertEqual(sha(folder/'best.pt'), result['references'][result['best_epoch']-1]['sha256'])

    def test_checkpoint_safe_reload_restores_model_and_optimizer(self):
        ref = self.runs[42]['references'][0]
        model = tiny_model(44)
        optimizer = torch.optim.AdamW(model.parameters(), lr=2e-5, weight_decay=.01)
        loaded = load_v2(ref['path'], expected_sha256=ref['sha256'], model=model, tokenizer=self.tokenizer,
                         optimizer=optimizer, fixture=True)
        self.assertEqual(optimizer.state_dict()['param_groups'], loaded['optimizer_state_dict']['param_groups'])
        for key, value in loaded['model_state_dict'].items():
            self.assertTrue(torch.equal(model.state_dict()[key], value))

    def test_checkpoint_still_valid_under_original_pr35_schema(self):
        from risk_speech_ai.checkpoint import validate_checkpoint_metadata
        ref = self.runs[42]['references'][0]
        loaded = load_v2(ref['path'], expected_sha256=ref['sha256'], fixture=True)
        self.assertEqual(validate_checkpoint_metadata(loaded)['checkpoint_schema_version'], 'v1')

    def test_reloaded_inference_matches_stored_logits(self):
        ref = self.runs[42]['references'][0]
        model, _ = model_for_inference(ref['path'], expected_sha256=ref['sha256'], tokenizer=self.tokenizer, fixture=True)
        current = infer_partition(model, self.tokenizer, self.parts['validation'], seed=42, epoch=1, arm='B_ratio')
        saved = read(Path(ref['path']).parent / 'validation_epoch_001.json')
        np.testing.assert_allclose(current['logits'], saved['logits'], atol=0, rtol=0)
        metrics = evaluate_logits(self.parts['validation'].rows, current['logits'])
        self.assertEqual(metrics, read(Path(ref['path']).parent/'epoch_001_metrics.json')['validation'])

    def test_validation_never_updates_weights_or_optimizer(self):
        model = tiny_model(42).train()
        before = {k: t.clone() for k, t in model.state_dict().items()}
        infer_partition(model, self.tokenizer, self.parts['validation'], seed=42, epoch=1, arm='B_ratio')
        self.assertTrue(model.training)
        self.assertTrue(all(torch.equal(before[k], t) for k, t in model.state_dict().items()))
        self.assertTrue(all(p.grad is None for p in model.parameters()))

    def test_single_sigmoid_matches_actual_inference(self):
        values = np.zeros((2, 9))
        values[0, 0] = 2.
        converted = probabilities(values)
        self.assertAlmostEqual(converted[0, 0], torch.sigmoid(torch.tensor(2.)).item(), places=6)
        self.assertEqual(converted[1, 0], .5)

    def test_threshold_support_and_tie_to_point5(self):
        selected = select_thresholds(predictions(self.parts['validation']), self.parts['validation'])
        self.assertEqual(selected['values'], [.5]*9)
        self.assertTrue(selected['support'][0]['tuned'])
        self.assertTrue(selected['support'][1]['tuned'])
        self.assertFalse(selected['support'][2]['tuned'])

    def test_threshold_second_tie_prefers_higher(self):
        by_seed = predictions(self.parts['validation'])
        # Positive probability .6; negative probability .45: perfect thresholds .50,.55,.60.
        # Force equal maxima .45/.55 by controlling the scalar F1 oracle; both distances .05.
        import expanded_selection as selection
        def oracle(y, p, threshold):
            return {'f1': 1. if threshold in (.45, .55) else 0.}
        with patch.object(selection, 'binary_metrics', side_effect=oracle):
            self.assertEqual(select_thresholds(by_seed, self.parts['validation'])['values'][0], .55)

    def test_seed_mean_rather_than_single_seed_selection(self):
        by_seed = predictions(self.parts['validation'])
        # Two seeds need .70, one prefers .50: pooled / single-seed selection must not override the mean.
        for seed, item in by_seed.items():
            for i, row in enumerate(self.parts['validation'].rows):
                item['logits'][i][0] = float(torch.logit(torch.tensor(.8 if row['is_phishing'] else (.67 if seed != 42 else .2))))
        self.assertEqual(select_thresholds(by_seed, self.parts['validation'])['values'][0], .7)

    def test_epoch_seed_mean_tie_prefers_earlier(self):
        p = {epoch: predictions(self.parts['validation'], epoch=epoch) for epoch in (1, 2, 3)}
        self.assertEqual(select_epoch(p, self.parts['validation'])['epoch'], 1)
        p[1][42]['logits'][0][0] = -2.
        self.assertEqual(select_epoch(p, self.parts['validation'])['epoch'], 2)

    def test_select_rejects_test_train_preflight_and_missing_seeds(self):
        val = self.parts['validation']
        for role in ('test', 'train'):
            with self.assertRaises(GateError):
                select_thresholds(predictions(replace(val, role=role)), replace(val, role=role))
        with self.assertRaises(GateError):
            select_thresholds(predictions(val), replace(val, authorized=False))
        small = predictions(val)
        del small[44]
        with self.assertRaises(GateError):
            select_thresholds(small, val)

    def test_metrics_false_alerts_misses_and_support(self):
        val = self.parts['validation']
        logits = predictions(val)[42]['logits']
        logits[0][0] = -2.  # risky conversation missed
        logits[-1][0] = 2.  # normal hard negative falsely flagged
        m = evaluate_logits(val.rows, logits)
        self.assertEqual(m['binary']['confusion_matrix'], [[11, 1], [1, 11]])
        self.assertAlmostEqual(m['binary']['fpr'], 1/12)
        self.assertAlmostEqual(m['binary']['fnr'], 1/12)
        self.assertEqual(m['hard_negative']['fp'], 1)
        self.assertEqual(m['conversations']['normal_false_alerts'], 1)
        self.assertEqual(m['conversations']['risky_missed'], 1)
        self.assertEqual(m['per_type']['institution_impersonation']['positive_families'], 12)
        self.assertIsNone(m['per_type']['secrecy']['f1'])
        self.assertIsNone(m['macro']['full8_f1'])

    def test_vector_thresholds_types_not_binary_gated(self):
        val = self.parts['validation']
        logits = predictions(val)[42]['logits']
        logits[0][0] = -10.
        metric = evaluate_logits(val.rows, logits, [.8]+[.5]*8)
        self.assertEqual(metric['per_type']['institution_impersonation']['fn'], 0)
        self.assertEqual(metric['binary']['fn'], 1)

    def test_seed_summary_and_paired_bootstrap(self):
        val = self.parts['validation']
        p = predictions(val)
        metrics = {seed: evaluate_logits(val.rows, item['logits']) for seed, item in p.items()}
        self.assertEqual(seed_summary(metrics)['/binary/f1']['std_sample'], 0.)
        boot = paired_bootstrap(p, p, val, repetitions=30)
        self.assertEqual(boot['ci95'], [0., 0.])
        self.assertEqual(boot, paired_bootstrap(p, p, val, repetitions=30))

    def test_prediction_alignment_and_nan_rejected(self):
        p = predictions(self.parts['validation'])[42]
        p['row_keys'].reverse()
        with self.assertRaises(GateError):
            validate_predictions(p, self.parts['validation'])
        with self.assertRaises(GateError):
            probabilities([[float('inf')]*9])

    def test_unauthorized_train_and_validation_rejected_before_model(self):
        for field in ('train', 'validation'):
            parts = dict(self.parts)
            parts[field] = replace(parts[field], authorized=False)
            with self.assertRaises(GateError), patch('expanded_assets.fresh_public_model') as factory:
                train(compile_runtime('A0', 42), parts['train'], parts['validation'], self.tokenizer,
                      run_id='must-not-run', receipt=parts['receipt'])
            factory.assert_not_called()

    def test_missing_manifest_never_synthesized(self):
        path = self.root/'absent.json'
        with self.assertRaises(GateError):
            load_partition(self.root, path, 'train', fixture=True)
        self.assertFalse(path.exists())

    def test_test_early_access_rejected_before_read(self):
        with patch('expanded_data.read') as reader:
            with self.assertRaises(GateError):
                load_partition(self.root, self.parts['validation'].manifest_path, 'test', fixture=True)
        reader.assert_not_called()

    def test_split_family_source_author_leakage_rejected(self):
        original = read(self.root/'split.json')
        for field in ('scenario_family_id', 'source_id', 'author_id'):
            plan = copy.deepcopy(original)
            plan['conversations']['FIXTURE_validation_000'][field] = plan['conversations']['FIXTURE_train_000'][field]
            with self.assertRaises(GateError):
                validate_split(plan)

    def test_preflight_does_not_grant_authorization(self):
        val = load_partition(self.root, self.parts['validation'].manifest_path, 'validation', mode='preflight', fixture=True)
        self.assertFalse(val.authorized)
        with self.assertRaises(GateError):
            val.verify({'validation'})

    def test_checkpoint_file_metadata_and_approval_tamper_rejected(self):
        ref = self.runs[42]['references'][0]
        with self.assertRaises(GateError):
            load_v2(ref['path'], expected_sha256='0'*64, fixture=True)
        payload = load_v2(ref['path'], expected_sha256=ref['sha256'], fixture=True)
        bad = copy.deepcopy(payload)
        bad['expanded_metadata']['optimizer_steps'] += 1
        with self.assertRaises(GateError):
            validate_extended(bad, fixture=True)
        with self.assertRaises(GateError):
            validate_extended(payload, bindings={'train': 'different'}, fixture=True)

    def test_fixture_checkpoint_cannot_load_as_production(self):
        ref = self.runs[42]['references'][0]
        with self.assertRaises(GateError):
            load_v2(ref['path'], expected_sha256=ref['sha256'])

    def test_overwrite_v1_path_and_run_escape_blocked(self):
        with self.assertRaises(FileExistsError):
            RunStore('B_ratio', 42, 'fixture-B', fixture=True, root=self.root/'runs')
        with self.assertRaises(GateError):
            RunStore('A0', 42, '../v1', fixture=True, root=self.root/'runs')
        with self.assertRaises(GateError):
            RunStore('A0', 42, 'v1', root=ROOT/'checkpoints')
        target = self.root/'sentinel.bin'
        target.write_bytes(b'keep')
        with self.assertRaises(FileExistsError):
            publish(target, lambda stream: stream.write(b'overwrite'))
        self.assertEqual(target.read_bytes(), b'keep')

    def test_failed_write_never_publishes_partial_file(self):
        target = self.root/'failed.bin'
        def fail(stream):
            stream.write(b'partial')
            raise OSError('simulated disk failure')
        with self.assertRaises(OSError):
            publish(target, fail)
        self.assertFalse(target.exists())

    def test_c_and_step_matched_use_b_frozen_recipe(self):
        val = self.parts['validation']
        pred = {epoch: {seed: read(Path(run['references'][epoch-1]['path']).parent/f'validation_epoch_{epoch:03d}.json')
                         for seed, run in self.runs.items()} for epoch in (1, 2, 3)}
        chosen = select_epoch(pred, val)['epoch']
        weights = self.runs[42]['weights']
        frozen = freeze_b(pred, val, weights, self.parts['train'].bindings, version='fixture-selection-v1',
                          checkpoints={str(s): self.runs[s]['references'][chosen-1] for s in SEEDS})
        for arm in ('C_approved', 'B_step_matched'):
            config = compile_runtime(arm, 42, frozen=frozen)
            validate_runtime(config)
            with warnings.catch_warnings(), patch('expanded_training.positive_weights', side_effect=AssertionError('C must not recompute weights')):
                warnings.simplefilter('ignore')
                result = train(config, self.parts['train'], val, self.tokenizer, run_id='fixture-C-control',
                               synthetic=self.parts['synthetic_train'], receipt=self.parts['receipt'],
                               store_root=self.root/'runs', fixture_model_factory=tiny_model)
            self.assertEqual(result['weights'], weights)
            self.assertEqual(result['initial_heads_sha256'], self.runs[42]['initial_heads_sha256'])
            self.assertEqual(result['optimizer_steps'], 4*chosen)
        path = self.root/'selection.json'
        save_selection(path, frozen)
        self.assertEqual(read(path)['thresholds'], frozen['thresholds'])
        with self.assertRaises(FileExistsError):
            save_selection(path, frozen)
        with self.assertRaises(GateError):
            train(compile_runtime('C_approved', 42, frozen=frozen), self.parts['train'], val, self.tokenizer,
                  run_id='zero-approved', receipt=self.parts['receipt'], fixture_model_factory=tiny_model,
                  store_root=self.root/'runs')

    def test_actual_unapproved_candidates_cannot_enter_train_cli(self):
        from expanded_cli import main
        stream = io.StringIO()
        with patch('sys.stdout', stream):
            status = main(['train', '--arm', 'C_approved', '--run-id', 'no-real-training'])
        self.assertEqual(status, 2)
        self.assertIn('BLOCKED', stream.getvalue())

    def test_select_cli_reinfers_fixture_checkpoints_before_freezing(self):
        import expanded_cli as cli
        import expanded_checkpoint as checkpoints
        import expanded_selection as selections
        index = dict(schema='expanded-prediction-index/1', epochs={})
        for epoch in (1, 2, 3):
            index['epochs'][str(epoch)] = {}
            for seed, run in self.runs.items():
                path = Path(run['references'][epoch-1]['path']).parent/f'validation_epoch_{epoch:03d}.json'
                index['epochs'][str(epoch)][str(seed)] = reference(self.root, path)
        index_path = write_json(self.root/'fixture-prediction-index.json', index)
        bundle_path = write_json(self.root/'fixture-cli-inputs.json', {'schema': 'expanded-inputs/1'})
        output = self.root/'fixture-cli-selected.json'
        original_load, original_model, original_check = checkpoints.load_v2, checkpoints.model_for_inference, selections.validate_frozen_checkpoints
        def fixture_load(*args, **kwargs):
            kwargs['fixture'] = True
            return original_load(*args, **kwargs)
        def fixture_model(*args, **kwargs):
            kwargs['fixture'] = True
            return original_model(*args, **kwargs)
        # Only the production/fixture boundary is adapted; inference, metrics, hashes and selector remain real.
        with patch.object(cli, 'ROOT', self.root), patch.object(cli, 'OUTPUT', self.root/'runs'), \
             patch.object(cli, 'partitions', return_value=(self.parts['train'], self.parts['validation'], None, self.parts['receipt'])), \
             patch.object(cli, 'tokenizer', return_value=self.tokenizer), \
             patch.object(checkpoints, 'load_v2', side_effect=fixture_load), \
             patch.object(checkpoints, 'model_for_inference', side_effect=fixture_model), \
             patch.object(selections, 'validate_frozen_checkpoints', side_effect=lambda value: original_check(value, fixture=True)), \
             patch('sys.stdout', io.StringIO()):
            result = cli.main(['select', '--arm', 'B_ratio', '--run-id', 'fixture-cli-selected',
                               '--inputs', str(bundle_path), '--prediction-index', str(index_path), '--output', str(output)])
        self.assertEqual(result, 0)
        selected = read(output)
        validate_frozen(selected)
        self.assertEqual(selected['weights'], self.runs[42]['weights'])

    def test_a0_a_epoch_run_actual_fixture_updates(self):
        for arm, count in [('A0', 1), ('A_epoch', 3)]:
            result = train(compile_runtime(arm, 42), self.parts['train'], self.parts['validation'], self.tokenizer,
                           run_id='fixture-A', receipt=self.parts['receipt'], store_root=self.root/'runs',
                           fixture_model_factory=tiny_model)
            self.assertEqual(len(result['history']), count)
            self.assertEqual(result['weights'], [1.]*8)
            self.assertEqual(result['initial_heads_sha256'], self.runs[42]['initial_heads_sha256'])

    def test_individual_human_rights_and_final_use_gates(self):
        cases = ('one_reviewer', 'same_reviewer', 'no_agreement', 'no_use', 'no_permission', 'partial_scope', 'wrong_data_hash')
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                parts = make_fixture(root)
                approval_path = root/'train-approval.json'
                approval = read(approval_path)
                if case == 'one_reviewer': approval['reviews'].pop()
                elif case == 'same_reviewer': approval['reviews'][1]['by'] = approval['reviews'][0]['by']
                elif case == 'no_agreement': approval['final_agreement']['approved'] = False
                elif case == 'no_use': approval['use_decision']['approved'] = False
                elif case == 'no_permission': next(iter(approval['permissions'].values()))['approved'] = False
                elif case == 'partial_scope': approval['reviews'][0]['scope_keys'].pop()
                elif case == 'wrong_data_hash': approval['data_sha256'] = '0'*64
                approval_path.write_text(json.dumps(approval, ensure_ascii=False), encoding='utf-8')
                manifest_path = parts['train'].manifest_path
                manifest = read(manifest_path)
                manifest['approval'] = reference(root, approval_path)
                manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding='utf-8')
                with self.assertRaises(GateError):
                    load_partition(root, manifest_path, 'train', fixture=True)

    def test_c_zero_rows_fail_closed_even_with_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parts = make_fixture(root)
            data = root/'synthetic_train.jsonl'
            data.write_text('', encoding='utf-8')
            manifest_path = parts['synthetic_train'].manifest_path
            manifest = read(manifest_path)
            manifest['data'] = reference(root, data)
            manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
            with self.assertRaisesRegex(GateError, 'Empty dataset'):
                load_partition(root, manifest_path, 'synthetic_train', fixture=True)

    def test_changed_evidence_cannot_reuse_loaded_partition(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parts = make_fixture(root)
            (root/'fixture-evidence.txt').write_text('changed', encoding='utf-8')
            with self.assertRaises(GateError):
                parts['train'].verify({'train'})


if __name__ == '__main__':
    unittest.main()
