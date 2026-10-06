"""Contract tests for phase-2 label and tuned-text preparation."""

import unittest

from risk_speech_ai.labels import ID2LABEL, LABEL2ID, LABELS, NUM_LABELS, to_multi_hot
from risk_speech_ai.training_data import build_training_samples


def label(utterance_id, *, conversation_id="P0001", status="reviewed", phishing=True, types=None):
    return {
        "conversation_id": conversation_id,
        "utterance_id": utterance_id,
        "label_status": status,
        "is_phishing": phishing,
        "labels": ["money_transfer"] if types is None else types,
    }


def tuned(utterance_id, *, conversation_id="P0001", text=None):
    return {
        "conversation_id": conversation_id,
        "utterance_id": utterance_id,
        "tuned_text": f"speech {utterance_id}" if text is None else text,
        "raw_text": "must not enter a model sample",
        "masked_text": "also not input",
    }


class LabelMappingTests(unittest.TestCase):
    def test_canonical_order_and_one_label(self):
        expected = (
            "institution_impersonation", "money_transfer", "personal_information",
            "app_installation", "secrecy", "threat_pressure", "loan_fraud",
            "information_probing",
        )
        self.assertEqual(expected, LABELS)
        self.assertEqual(dict(enumerate(expected)), ID2LABEL)
        self.assertEqual({name: index for index, name in enumerate(expected)}, LABEL2ID)
        for index, name in enumerate(expected):
            target = to_multi_hot([name])
            self.assertEqual(8, len(target))
            self.assertEqual([index], [i for i, value in enumerate(target) if value])
        self.assertEqual(8, NUM_LABELS)
        self.assertEqual("institution_impersonation", LABELS[0])
        self.assertEqual("information_probing", ID2LABEL[7])
        self.assertEqual(1, LABEL2ID["money_transfer"])
        self.assertEqual([0, 1, 0, 0, 0, 0, 0, 0], to_multi_hot(["money_transfer"]))

    def test_multiple_duplicate_empty_and_unknown(self):
        self.assertEqual([0, 1, 0, 0, 1, 0, 0, 0], to_multi_hot(["money_transfer", "secrecy"]))
        self.assertEqual([0, 1, 0, 0, 0, 0, 0, 0], to_multi_hot(["money_transfer"] * 2))
        self.assertEqual([0] * 8, to_multi_hot([]))
        with self.assertRaisesRegex(ValueError, "unknown label"):
            to_multi_hot(["unknown"])


class StatusTests(unittest.TestCase):
    def test_normal_with_risk_type_is_rejected(self):
        result = build_training_samples([label(1, phishing=False)], [tuned(1)])
        self.assertEqual([], result.samples)
        self.assertEqual(1, result.statistics["invalid_label"])

    def test_invalid_field_types_and_status_are_rejected(self):
        for override in ({"is_phishing": 1}, {"is_phishing": "false"},
                         {"labels": "money_transfer"}, {"labels": [None]},
                         {"label_status": "approved"}):
            with self.subTest(override=override):
                result = build_training_samples([dict(label(1), **override)], [tuned(1)])
                self.assertEqual([], result.samples)
                self.assertEqual(1, result.statistics["invalid_label"])

    def test_reviewed_normal_and_phishing(self):
        result = build_training_samples(
            [label(1, phishing=False, types=[]), label(2, types=["money_transfer", "secrecy"])],
            [tuned(1), tuned(2)],
        )
        self.assertEqual([0.0, 1.0], [sample.risk_target for sample in result.samples])
        self.assertEqual([0] * 8, result.samples[0].type_targets)
        self.assertEqual([0, 1, 0, 0, 1, 0, 0, 0], result.samples[1].type_targets)

    def test_out_of_taxonomy_valid_and_invalid(self):
        result = build_training_samples(
            [
                label(1, status="out_of_taxonomy", types=[]),
                label(2, status="out_of_taxonomy", phishing=False, types=[]),
                label(3, status="out_of_taxonomy"),
            ],
            [tuned(1), tuned(2), tuned(3)],
        )
        self.assertEqual([1], [sample.utterance_id for sample in result.samples])
        self.assertEqual(1.0, result.samples[0].risk_target)
        self.assertEqual([0] * 8, result.samples[0].type_targets)
        self.assertEqual(2, result.statistics["invalid_label"])

    def test_unreviewed_and_missing_status_are_excluded(self):
        no_status = label(2, types=[])
        del no_status["label_status"]
        result = build_training_samples(
            [label(1, status="unreviewed"), no_status], [tuned(1), tuned(2)]
        )
        self.assertEqual([], result.samples)
        self.assertEqual(1, result.statistics["excluded_unreviewed"])
        self.assertEqual(1, result.statistics["excluded_missing_status"])

    def test_reviewed_phishing_without_type_is_invalid(self):
        result = build_training_samples([label(1, types=[])], [tuned(1)])
        self.assertEqual(1, result.statistics["invalid_label"])


class JoinTests(unittest.TestCase):
    def test_invalid_unmatched_tuned_text_is_reported(self):
        result = build_training_samples(
            [label(4)],
            [tuned(1, text=" "), dict(tuned(2), tuned_text=None),
             {"conversation_id": "P0001", "utterance_id": 3}, tuned(4)],
        )
        self.assertEqual(3, result.statistics["missing_label"])
        self.assertEqual(1, result.statistics["empty_tuned_text"])
        self.assertEqual(2, result.statistics["missing_tuned_text"])
        self.assertEqual([], result.samples[0].history_texts)

    def test_duplicate_tuned_key_cannot_be_current_or_history(self):
        result = build_training_samples(
            [label(1), label(2)], [tuned(1, text="a"), tuned(1, text="b"), tuned(2)]
        )
        self.assertEqual(1, result.statistics["duplicate_key"])
        self.assertEqual([2], [sample.utterance_id for sample in result.samples])
        self.assertEqual([], result.samples[0].history_texts)

    def test_match_uses_composite_key_and_text_only(self):
        result = build_training_samples(
            [label(2), label(1, conversation_id="P0002")],
            [tuned(1, conversation_id="P0002"), tuned(2)],
        )
        self.assertEqual(2, result.statistics["matched"])
        self.assertEqual("speech 2", result.samples[0].current_text)
        self.assertNotIn("must not enter", repr(result.samples))

    def test_missing_sides_and_empty_text(self):
        result = build_training_samples(
            [label(1), label(2), label(4)],
            [tuned(1), tuned(3), tuned(4, text=" ")],
        )
        self.assertEqual(1, result.statistics["missing_tuned_text"])
        self.assertEqual(1, result.statistics["missing_label"])
        self.assertEqual(1, result.statistics["empty_tuned_text"])
        self.assertEqual([1], [sample.utterance_id for sample in result.samples])

    def test_matched_row_without_tuned_text_is_reported(self):
        result = build_training_samples(
            [label(1)], [{"conversation_id": "P0001", "utterance_id": 1}]
        )
        self.assertEqual(1, result.statistics["matched"])
        self.assertEqual(1, result.statistics["missing_tuned_text"])
        self.assertEqual([], result.samples)

    def test_mismatched_conversation_or_utterance_is_reported_as_missing_pairs(self):
        result = build_training_samples([label(1)], [tuned(2, conversation_id="P0002")])
        self.assertEqual(0, result.statistics["matched"])
        self.assertEqual(1, result.statistics["missing_tuned_text"])
        self.assertEqual(1, result.statistics["missing_label"])

    def test_duplicate_key_excludes_ambiguous_rows(self):
        result = build_training_samples([label(1), label(1)], [tuned(1)])
        self.assertEqual(1, result.statistics["duplicate_key"])
        self.assertEqual([], result.samples)

    def test_unknown_label_is_reported(self):
        result = build_training_samples([label(1, types=["unknown"])], [tuned(1)])
        self.assertEqual(1, result.statistics["invalid_label"])


class HistoryTests(unittest.TestCase):
    def test_ambiguous_chronological_aliases_are_rejected(self):
        for first, second in (("U2", "U002"), (2, "U2")):
            with self.subTest(first=first, second=second):
                with self.assertRaisesRegex(ValueError, "ambiguous utterance order"):
                    build_training_samples([label(10)], [tuned(first), tuned(second), tuned(10)])

    def test_unsupported_ids_fail_instead_of_guessing_order(self):
        for value in (True, 0, -1, 1.5, "2", "utterance_2", "U0", None):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    build_training_samples([label(value)], [tuned(value)])

    def test_integer_order_and_current_target_are_independent_of_history_label(self):
        result = build_training_samples(
            [label(2), label(10, phishing=False, types=[])],
            [tuned(11), tuned(10), tuned(2), tuned(1)],
        )
        current = result.samples[-1]
        self.assertEqual(10, current.utterance_id)
        self.assertEqual(["speech 1", "speech 2"], current.history_texts)
        self.assertEqual(0.0, current.risk_target)
        self.assertEqual([0] * 8, current.type_targets)

    def test_first_second_sixth_and_seventh(self):
        result = build_training_samples(
            [label(i) for i in range(1, 8)],
            [tuned(i) for i in (7, 5, 3, 1, 6, 4, 2)],
        )
        history = {sample.utterance_id: sample.history_texts for sample in result.samples}
        self.assertEqual([], history[1])
        self.assertEqual(["speech 1"], history[2])
        self.assertEqual([f"speech {i}" for i in range(1, 6)], history[6])
        self.assertEqual([f"speech {i}" for i in range(2, 7)], history[7])

    def test_other_conversation_and_future_do_not_leak(self):
        result = build_training_samples(
            [label(4)],
            [tuned(1), tuned(3), tuned(4), tuned(5), tuned(2, conversation_id="P0002")],
        )
        self.assertEqual(["speech 1", "speech 3"], result.samples[0].history_texts)

    def test_history_text_can_have_no_label(self):
        result = build_training_samples([label(2)], [tuned(1), tuned(2)])
        self.assertEqual(["speech 1"], result.samples[0].history_texts)

    def test_u_prefixed_ids_order_numerically(self):
        result = build_training_samples(
            [label("U004")], [tuned("U004"), tuned("U002"), tuned("U001"), tuned("U003")]
        )
        self.assertEqual(["speech U001", "speech U002", "speech U003"], result.samples[0].history_texts)

    def test_unpadded_u_ids_are_not_sorted_lexically(self):
        result = build_training_samples(
            [label("U10")], [tuned("U10"), tuned("U2"), tuned("U009")]
        )
        self.assertEqual(["speech U2", "speech U009"], result.samples[0].history_texts)

    def test_zero_padded_u_ids_are_sorted_numerically(self):
        result = build_training_samples(
            [label("U010")], [tuned("U010"), tuned("U009")]
        )
        self.assertEqual(["speech U009"], result.samples[0].history_texts)


if __name__ == "__main__":
    unittest.main()
