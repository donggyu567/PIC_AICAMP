"""Tests for strict parsing of LLM correction responses."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from models.llm_correction import LLMResponseError, parse_correction_response
from models.llm_correction.parser import MAX_LLM_RESPONSE_CHARS


class CorrectionResponseParserTests(unittest.TestCase):
    def test_accepts_exact_json_shape(self) -> None:
        parsed = parse_correction_response(
            '{"tuned_text":"안녕하세요.","unclear_segments":[]}'
        )

        self.assertEqual("안녕하세요.", parsed.tuned_text)
        self.assertEqual((), parsed.unclear_segments)

    def test_rejects_markdown_code_fences(self) -> None:
        response = (
            "```json\n"
            '{"tuned_text":"안녕하세요.","unclear_segments":[]}\n'
            "```"
        )

        with self.assertRaisesRegex(LLMResponseError, "valid JSON"):
            parse_correction_response(response)

    def test_rejects_unexpected_fields(self) -> None:
        response = (
            '{"tuned_text":"안녕하세요.","unclear_segments":[],'
            '"is_tuned":true}'
        )

        with self.assertRaisesRegex(LLMResponseError, "unexpected"):
            parse_correction_response(response)

    def test_rejects_missing_fields(self) -> None:
        with self.assertRaisesRegex(LLMResponseError, "missing"):
            parse_correction_response('{"tuned_text":"안녕하세요."}')

    def test_rejects_duplicate_fields(self) -> None:
        response = (
            '{"tuned_text":"첫 번째","tuned_text":"두 번째",'
            '"unclear_segments":[]}'
        )

        with self.assertRaisesRegex(LLMResponseError, "duplicate"):
            parse_correction_response(response)

    def test_rejects_non_string_unclear_segments(self) -> None:
        response = (
            '{"tuned_text":"[불명확]","unclear_segments":[123]}'
        )

        with self.assertRaisesRegex(LLMResponseError, "non-blank strings"):
            parse_correction_response(response)

    def test_rejects_trailing_explanation(self) -> None:
        response = (
            '{"tuned_text":"안녕하세요.","unclear_segments":[]}'
            " 보정을 완료했습니다."
        )

        with self.assertRaisesRegex(LLMResponseError, "valid JSON"):
            parse_correction_response(response)

    def test_rejects_non_standard_json_constants(self) -> None:
        response = '{"tuned_text":NaN,"unclear_segments":[]}'

        with self.assertRaisesRegex(LLMResponseError, "non-standard"):
            parse_correction_response(response)

    def test_rejects_an_oversized_response_before_parsing(self) -> None:
        response = "x" * (MAX_LLM_RESPONSE_CHARS + 1)

        with self.assertRaisesRegex(LLMResponseError, "allowed length"):
            parse_correction_response(response)

    def test_normalizes_a_deeply_nested_json_failure(self) -> None:
        with patch(
            "models.llm_correction.parser.json.loads",
            side_effect=RecursionError,
        ):
            with self.assertRaisesRegex(LLMResponseError, "valid JSON"):
                parse_correction_response("{}")


if __name__ == "__main__":
    unittest.main()
