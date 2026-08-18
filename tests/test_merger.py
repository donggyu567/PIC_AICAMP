"""Tests for task 1 masked and task 2 tuned utterance merging."""

from __future__ import annotations

import unittest

from risk_speech_ai.loader import InputDataError
from risk_speech_ai.merger import merge_utterance


def masked_result(**overrides: object) -> dict[str, object]:
    result: dict[str, object] = {
        "utterance_id": 4,
        "masked_text": "[이름] 씨 [전화번호] 번호 맞으시죠",
        "has_masked_data": True,
        "masked_types": ["PERSON", "PHONE_NUMBER"],
    }
    result.update(overrides)
    return result


def tuned_result(**overrides: object) -> dict[str, object]:
    result: dict[str, object] = {
        "utterance_id": 4,
        "tuned_text": "[이름] 씨 [전화번호] 번호 맞으시죠.",
        "is_tuned": True,
        "has_unclear": False,
        "unclear_segments": [],
    }
    result.update(overrides)
    return result


class MergeUtteranceTests(unittest.TestCase):
    def test_merges_and_preserves_masked_and_tuned_values(self) -> None:
        utterance = merge_utterance(masked_result(), tuned_result())

        self.assertEqual(4, utterance.utterance_id)
        self.assertEqual("[이름] 씨 [전화번호] 번호 맞으시죠", utterance.masked_text)
        self.assertTrue(utterance.has_masked_data)
        self.assertEqual(["PERSON", "PHONE_NUMBER"], utterance.masked_types)
        self.assertEqual(
            "[이름] 씨 [전화번호] 번호 맞으시죠.", utterance.tuned_text
        )
        self.assertTrue(utterance.is_tuned)
        self.assertFalse(utterance.has_unclear)
        self.assertEqual([], utterance.unclear_segments)

    def test_final_result_does_not_include_raw_text(self) -> None:
        masked = masked_result(raw_text="홍길동 010-1234-5678")

        payload = merge_utterance(masked, tuned_result()).to_dict()

        self.assertNotIn("raw_text", payload)

    def test_rejects_utterance_id_mismatch(self) -> None:
        with self.assertRaisesRegex(InputDataError, "does not match"):
            merge_utterance(masked_result(utterance_id=5), tuned_result())

    def test_rejects_each_missing_masked_field(self) -> None:
        for field in (
            "utterance_id",
            "masked_text",
            "has_masked_data",
            "masked_types",
        ):
            with self.subTest(field=field):
                result = masked_result()
                del result[field]
                with self.assertRaises(InputDataError):
                    merge_utterance(result, tuned_result())

    def test_rejects_invalid_masked_field_types(self) -> None:
        invalid_results = {
            "utterance_id": masked_result(utterance_id=True),
            "masked_text": masked_result(masked_text=4),
            "has_masked_data": masked_result(has_masked_data=1),
            "masked_types_not_list": masked_result(masked_types="PERSON"),
            "masked_types_item": masked_result(masked_types=[1]),
        }

        for field, result in invalid_results.items():
            with self.subTest(field=field):
                with self.assertRaises(InputDataError):
                    merge_utterance(result, tuned_result())

    def test_rejects_non_mapping_masked_result(self) -> None:
        with self.assertRaises(InputDataError):
            merge_utterance("masked text", tuned_result())  # type: ignore[arg-type]

    def test_rejects_each_missing_tuned_field(self) -> None:
        for field in (
            "utterance_id",
            "tuned_text",
            "is_tuned",
            "has_unclear",
            "unclear_segments",
        ):
            with self.subTest(field=field):
                result = tuned_result()
                del result[field]
                with self.assertRaises(InputDataError):
                    merge_utterance(masked_result(), result)

    def test_rejects_invalid_tuned_field_types(self) -> None:
        invalid_results = {
            "utterance_id": tuned_result(utterance_id=True),
            "tuned_text": tuned_result(tuned_text=4),
            "is_tuned": tuned_result(is_tuned="true"),
            "has_unclear": tuned_result(has_unclear=1),
            "unclear_segments_not_list": tuned_result(unclear_segments="불명확"),
            "unclear_segments_item": tuned_result(unclear_segments=[1]),
        }

        for field, result in invalid_results.items():
            with self.subTest(field=field):
                with self.assertRaises(InputDataError):
                    merge_utterance(masked_result(), result)

    def test_rejects_invalid_unclear_segments_type(self) -> None:
        for value in ("불명확", [1]):
            with self.subTest(value=value):
                with self.assertRaises(InputDataError):
                    merge_utterance(
                        masked_result(), tuned_result(unclear_segments=value)
                    )
