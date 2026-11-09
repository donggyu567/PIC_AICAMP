"""Research/production isolation, provenance, hash and causal-input regression."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'experiments/koelectra_v2'))
from expanded_common import GateError, read
from expanded_data import load_partition
from stage3_data import BASE, LABELS, jsonl, validate, normalize, compare
from stage3_research import load_research, causal_samples


@unittest.skipUnless((BASE/'train_80_candidate.jsonl').is_file() and (BASE/'validation_32_synthetic.jsonl').is_file(), 'Internal research data intentionally not published')
class Stage3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.train = jsonl(BASE/'train_80_candidate.jsonl')
        cls.val = jsonl(BASE/'validation_32_synthetic.jsonl')

    def test_actual_counts_and_provisional_provenance(self):
        self.assertEqual(validate(self.train, expected=80)['utterances'], 656)
        self.assertEqual(validate(self.val, expected=32)['utterances'], 256)
        self.assertTrue(all(c['source_kind'] == 'llm_synthetic' for c in self.train+self.val))

    def test_test_denied_before_io(self):
        with patch('stage3_research.read') as reader:
            with self.assertRaises(GateError): load_research('test', mode='internal_experiment')
        reader.assert_not_called()

    def test_missing_research_mode_denied_before_io(self):
        with patch('stage3_research.read') as reader:
            with self.assertRaises(GateError): load_research('train', mode='authorized')
        reader.assert_not_called()

    def test_cannot_promote_research_manifest_to_production(self):
        with self.assertRaises(GateError):
            load_partition(BASE, BASE/'data_use_manifest.json', 'train')

    def test_real_adapter_preserves_unapproved_status(self):
        research = load_research('train', mode='internal_experiment')
        self.assertEqual(len(research.samples), 656)
        self.assertFalse(research.human_review_complete)
        self.assertFalse(research.deployment_approved)
        self.assertFalse(hasattr(research, 'authorized'))
        self.assertFalse(hasattr(research, 'verify'))

    def test_hash_tamper_rejected(self):
        manifest = copy.deepcopy(read(BASE/'data_use_manifest.json'))
        manifest['train']['sha256'] = '0'*64
        with patch('stage3_research.read', return_value=manifest):
            with self.assertRaises(GateError): load_research('train', mode='internal_experiment')

    def test_label_order_tamper_rejected(self):
        manifest = copy.deepcopy(read(BASE/'data_use_manifest.json'))
        manifest['label_order'].reverse()
        with patch('stage3_research.read', return_value=manifest):
            with self.assertRaises(GateError): load_research('train', mode='internal_experiment')

    def test_false_approval_rejected(self):
        manifest = copy.deepcopy(read(BASE/'data_use_manifest.json'))
        manifest['deployment_approved'] = True
        with patch('stage3_research.read', return_value=manifest):
            with self.assertRaises(GateError): load_research('train', mode='internal_experiment')

    def test_every_history_is_past_only_and_conversation_local(self):
        for c in self.train+self.val:
            samples = causal_samples([c])
            for i, s in enumerate(samples):
                self.assertEqual(s.history_texts, [u['text'] for u in c['utterances'][max(0,i-5):i]])
                self.assertEqual(s.current_text, c['utterances'][i]['text'])
        a = copy.deepcopy(self.val[0]); b = copy.deepcopy(a)
        b['utterances'][-1]['text'] = 'future-only-marker'
        self.assertEqual(causal_samples([a])[:-1], causal_samples([b])[:-1])

    def test_privacy_link_and_digits_rejected(self):
        for text in ['https://example.invalid', '1234567890123', 'sample@example.invalid', '[UNKNOWN]']:
            data = copy.deepcopy(self.val[:1]); data[0]['utterances'][0]['text'] = text
            with self.assertRaises(GateError): validate(data)

    def test_disjoint_family_and_conversation_identifiers(self):
        for key in ['conversation_id', 'scenario_family_id']:
            self.assertFalse({c[key] for c in self.train} & {c[key] for c in self.val})
        bad = copy.deepcopy(self.val[:2]); bad[1]['scenario_family_id'] = bad[0]['scenario_family_id']
        with self.assertRaises(GateError): validate(bad)

    def test_label_vector_uses_canonical_order(self):
        for c in self.train+self.val:
            for u, sample in zip(c['utterances'], causal_samples([c])):
                self.assertEqual(sample.type_targets, [int(label in u['labels']) for label in LABELS])

    def test_normalized_duplicate_detection(self):
        self.assertEqual(normalize(' A, B! '), normalize('ab'))
        self.assertEqual(compare([('one', 'ab')], [('two', 'ab')])['candidate_count'], 1)


if __name__ == '__main__': unittest.main()
