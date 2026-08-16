"""Tests for task 1 and task 2 utterance merging."""

from __future__ import annotations

import unittest

from risk_speech_ai.loader import InputDataError
from risk_speech_ai.merger import merge_utterance


def tuned_result(**overrides: object) -> dict[str, object]:
    result: dict[str, object] = {
        "utterance_id": 4,
        "tuned_text": "보정된 문장",
        "is_tuned": True,
        "has_unclear": True,
        "unclear_segments": ["불명확 구간"],
    }
    result.update(overrides)
    return result


class MergeUtteranceTests(unittest.TestCase):
    def test_merges_and_preserves_required_values(self) -> None:
        result = tuned_result()

        utterance = merge_utterance("원본 STT 문장", result, raw_utterance_id=4)

        self.assertEqual(4, utterance.utterance_id)
        self.assertEqual("원본 STT 문장", utterance.raw_text)
        self.assertEqual("보정된 문장", utterance.tuned_text)
        self.assertTrue(utterance.is_tuned)
        self.assertTrue(utterance.has_unclear)
        self.assertEqual(["불명확 구간"], utterance.unclear_segments)

    def test_preserves_empty_unclear_segments(self) -> None:
        utterance = merge_utterance(
            "원본", tuned_result(has_unclear=False, unclear_segments=[])
        )

        self.assertEqual([], utterance.unclear_segments)

    def test_preserves_different_raw_and_tuned_text(self) -> None:
        utterance = merge_utterance(
            "지금 안전 계자로 이채하세요",
            tuned_result(
                tuned_text="지금 안전계좌로 이체하세요.",
                has_unclear=False,
                unclear_segments=[],
            ),
        )

        self.assertEqual("지금 안전 계자로 이채하세요", utterance.raw_text)
        self.assertEqual("지금 안전계좌로 이체하세요.", utterance.tuned_text)

    def test_rejects_each_missing_required_field(self) -> None:
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
                    merge_utterance("원본", result)

    def test_rejects_unsuitable_input(self) -> None:
        with self.assertRaises(InputDataError):
            merge_utterance(123, tuned_result())  # type: ignore[arg-type]

    def test_rejects_invalid_tuned_result_field_types(self) -> None:
        invalid_results = {
            "utterance_id": tuned_result(utterance_id="4"),
            "tuned_text": tuned_result(tuned_text=4),
            "is_tuned": tuned_result(is_tuned="true"),
            "has_unclear": tuned_result(has_unclear=1),
            "unclear_segments": tuned_result(unclear_segments=[1]),
        }

        for field, result in invalid_results.items():
            with self.subTest(field=field):
                with self.assertRaises(InputDataError):
                    merge_utterance("원본", result)

    def test_rejects_verifiable_id_mismatch(self) -> None:
        with self.assertRaises(InputDataError):
            merge_utterance("원본", tuned_result(utterance_id=4), raw_utterance_id=5)
