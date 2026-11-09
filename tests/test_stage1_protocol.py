"""Reject unsafe changes to the expansion design, without training or approval."""
import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'experiments/koelectra_v2'))
import validate_stage1 as design


class Stage1ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.cfg = json.loads(design.CONFIG.read_text(encoding='utf-8'))

    def test_valid_design_still_blocks_execution(self):
        result = design.validate(self.cfg)
        self.assertFalse(result['training_authorized'])
        self.assertEqual(len(result['missing_inputs']), 4)

    def test_execution_cannot_be_enabled(self):
        for key in self.cfg['execution']:
            cfg = copy.deepcopy(self.cfg)
            cfg['execution'][key] = True
            with self.assertRaises(ValueError):
                design.validate(cfg)

    def test_label_order_cannot_change(self):
        self.cfg['input']['label_order'].reverse()
        with self.assertRaises(ValueError):
            design.validate(self.cfg)

    def test_input_tamper_is_rejected(self):
        self.cfg['existing_inputs']['v1_labels']['sha256'] = '0' * 64
        with self.assertRaises(ValueError):
            design.validate(self.cfg)

    def test_test_selection_is_rejected(self):
        self.cfg['selection']['test_selection_allowed'] = True
        with self.assertRaises(ValueError):
            design.validate(self.cfg)

    def test_legacy_holdout_mix_rejected(self):
        self.cfg['data']['legacy_48_10_10_use'] = 'append_to_new_test'
        with self.assertRaises(ValueError):
            design.validate(self.cfg)

    def test_automatic_approval_rejected(self):
        self.cfg['data']['final_approved_synthetic_train_conversations'] = 24
        with self.assertRaises(ValueError):
            design.validate(self.cfg)

    def test_output_escape_rejected(self):
        self.cfg['output_plan']['root'] = '../checkpoints'
        with self.assertRaises(ValueError):
            design.validate(self.cfg)

    def test_original_weight_recipe_not_equivalent(self):
        self.cfg['training_plan']['weight_policy']['primary'] = 'min(5,sqrt(N_negative/N_positive))'
        with self.assertRaises(ValueError):
            design.validate(self.cfg)


if __name__ == '__main__':
    unittest.main()
