"""Additional parser, final registry and serialization guards; no model updates."""
from dataclasses import replace
import copy
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from expanded_fixtures import make_fixture, predictions
from expanded_common import GateError, LABELS, PROTOCOL_SHA, REVISION, read, write_json, compile_runtime
from expanded_selection import freeze_b, validate_frozen
from expanded_evaluation import validate_final_plan, threshold_vector
from expanded_data import load_partition, validate_receipt
from expanded_checkpoint import reconstruct_config


class ExpandedGuardTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.parts = make_fixture(self.root)

    def frozen(self):
        pred = {e: predictions(self.parts['validation'], epoch=e) for e in (1, 2, 3)}
        return freeze_b(pred, self.parts['validation'], [1.]*8, self.parts['train'].bindings,
                        version='UNIT-FIXTURE-ONLY', checkpoints={str(s): {'path': 'fixture-unused.pt', 'sha256': '0'*64} for s in (42, 43, 44)})

    def plan(self):
        frozen = self.frozen()
        entry = dict(checkpoint={'path': 'fixture-unused.pt', 'sha256': '0'*64}, epoch=1,
                     thresholds=[.5]*9, threshold_version='initial-0.5')
        return dict(schema='expanded-final-plan/1', protocol_sha256=PROTOCOL_SHA,
                    selection_source='validation', label_order=list(LABELS), frozen_b=frozen,
                    models={'A0': {str(s): copy.deepcopy(entry) for s in (42, 43, 44)}})

    def test_final_registry_can_register_a0_with_all_seeds(self):
        validate_final_plan(self.plan())

    def test_final_registry_cannot_select_from_test(self):
        plan = self.plan()
        plan['selection_source'] = 'test'
        with self.assertRaises(GateError): validate_final_plan(plan)

    def test_a0_final_registry_epoch_or_threshold_change_rejected(self):
        for field, value in [('epoch', 2), ('thresholds', [.4]*9)]:
            plan = self.plan()
            for entry in plan['models']['A0'].values(): entry[field] = value
            with self.assertRaises(GateError): validate_final_plan(plan)

    def test_final_registry_missing_seed_rejected(self):
        plan = self.plan()
        del plan['models']['A0']['44']
        with self.assertRaises(GateError): validate_final_plan(plan)

    def test_c_final_registry_must_preserve_b_threshold_version(self):
        for arm in ('C_approved', 'B_step_matched'):
            plan = self.plan()
            entries = plan['models'].pop('A0')
            plan['models'][arm] = entries
            with self.assertRaises(GateError): validate_final_plan(plan)

    def test_test_manifest_never_read_by_preflight(self):
        with patch('expanded_data.read') as reader:
            with self.assertRaises(GateError):
                load_partition(self.root, self.parts['validation'].manifest_path, 'test', mode='preflight', fixture=True)
        reader.assert_not_called()

    def test_selection_changed_protocol_or_labels_rejected(self):
        for field, value in [('protocol_sha256', '0'*64), ('label_order', list(reversed(LABELS))), ('source', 'test')]:
            frozen = self.frozen()
            frozen[field] = value
            with self.assertRaises(GateError): validate_frozen(frozen)

    def test_threshold_count_and_nan_rejected(self):
        for values in [[.5]*8, [.5]*8+[float('nan')], [.5]*8+[2.]]:
            with self.assertRaises(GateError): threshold_vector(values)

    def test_fixture_cannot_be_loaded_as_production_manifest(self):
        with self.assertRaises(GateError):
            load_partition(self.root, self.parts['train'].manifest_path, 'train')

    def test_missing_timezone_is_not_human_evidence(self):
        from expanded_data import decision
        with self.assertRaises(GateError):
            decision(dict(approved=True, purpose='training', by='UNIT FIXTURE', at='2026-11-09T12:00:00', evidence='mock'), 'training')

    def test_duplicate_keys_and_nonfinite_json_are_rejected(self):
        path = self.root/'bad.json'
        for content in ['{"role":"train","role":"test"}', '{"weight":NaN}']:
            path.write_text(content, encoding='utf-8')
            with self.assertRaises(GateError): read(path)

    def test_null_attention_serialization_roundtrip_preserves_strict_pr35_contract(self):
        from transformers import ElectraConfig
        cfg = ElectraConfig().to_dict()
        cfg['attn_implementation'] = None
        self.assertIn('attn_implementation', reconstruct_config(cfg).to_dict())

    def test_select_and_final_evaluate_cli_fail_without_authorization(self):
        from expanded_cli import main
        for mode in ('select', 'final-evaluate'):
            with patch('sys.stdout', io.StringIO()) as output:
                result = main([mode, '--run-id', 'no-data-no-authorization'])
            self.assertEqual(result, 2)
            self.assertIn('BLOCKED', output.getvalue())

    def test_final_model_must_validate_before_any_test_manifest_access(self):
        from types import SimpleNamespace
        import expanded_cli as cli
        import expanded_checkpoint as checkpoints
        model_path = self.root/'runs'/'invalid-model.pt'
        model_path.parent.mkdir()
        model_path.write_bytes(b'UNIT FIXTURE ONLY')
        selection = write_json(self.root/'frozen-fixture.json', self.frozen())
        bundle = write_json(self.root/'custodian-fixture-bundle.json', {'schema': 'expanded-inputs/1',
                            'test_receipt': {'path': 'never-open.json', 'sha256': '0'*64},
                            'test': {'path': 'never-open-test-manifest.json', 'sha256': '0'*64}})
        release = write_json(self.root/'unused-release.json', {'unit_fixture': True})
        args = SimpleNamespace(evaluation_root=self.root, release=release, checkpoint=model_path,
                               selection=selection, output=self.root/'new-final-report.json', inputs=bundle,
                               arm='B_ratio', seed=42, cache=self.root)
        with patch.object(cli, 'OUTPUT', self.root/'runs'), patch.object(cli, 'tokenizer', return_value=object()), \
             patch.object(checkpoints, 'model_for_inference', side_effect=GateError('metadata mismatch')), \
             patch.object(cli, 'load_partition') as loader:
            with self.assertRaisesRegex(GateError, 'metadata mismatch'):
                cli.final_evaluate(args)
        loader.assert_not_called()


if __name__ == '__main__':
    unittest.main()
