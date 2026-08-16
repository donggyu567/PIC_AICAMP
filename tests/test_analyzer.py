"""Tests for the model-independent analysis boundary."""

from __future__ import annotations

import unittest

from risk_speech_ai import RiskAssessment, analyze_risk
from risk_speech_ai.preprocessing import InvalidTextError


class FakeAssessor:
    def __init__(self) -> None:
        self.received_text: str | None = None

    def assess(self, text: str) -> RiskAssessment:
        self.received_text = text
        return RiskAssessment(reason="Result supplied by fake assessor")


class AnalyzeRiskTests(unittest.TestCase):
    def test_normal_string_is_passed_to_assessor(self) -> None:
        assessor = FakeAssessor()

        result = analyze_risk("고객 응대 내용을 확인합니다.", assessor=assessor)

        self.assertEqual("고객 응대 내용을 확인합니다.", assessor.received_text)
        self.assertEqual("Result supplied by fake assessor", result.reason)

    def test_surrounding_whitespace_is_removed_before_assessment(self) -> None:
        assessor = FakeAssessor()

        analyze_risk("  공백을 정리합니다.  ", assessor=assessor)

        self.assertEqual("공백을 정리합니다.", assessor.received_text)

    def test_empty_string_is_rejected(self) -> None:
        with self.assertRaises(InvalidTextError):
            analyze_risk("")

    def test_whitespace_only_string_is_rejected(self) -> None:
        with self.assertRaises(InvalidTextError):
            analyze_risk(" \t\n ")

    def test_non_string_input_is_rejected(self) -> None:
        for invalid_value in (None, 123, ["text"]):
            with self.subTest(invalid_value=invalid_value):
                with self.assertRaises(InvalidTextError):
                    analyze_risk(invalid_value)

    def test_default_assessor_does_not_make_a_risk_decision(self) -> None:
        result = analyze_risk("정책이 아직 확정되지 않았습니다.")

        self.assertIsNone(result.is_risky)
        self.assertIsNone(result.risk_level)
        self.assertIsNone(result.risk_score)


if __name__ == "__main__":
    unittest.main()
