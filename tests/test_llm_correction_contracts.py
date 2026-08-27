"""Contract tests for masked STT input and correction output."""

from __future__ import annotations

import unittest

from models.llm_correction import (
    ContractError,
    CorrectionResult,
    MaskedTranscript,
    validate_correction_against_input,
    validate_masking_token_preservation,
)


def valid_masked_transcript(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": "1.0",
        "conversation_id": "C0001",
        "utterance_id": 17,
        "masked_text": "[PERSON] 씨 지금 [ACCOUNT_NUMBER] 계좌로 송금하세요.",
        "has_masked_data": True,
        "masked_types": ["PERSON", "ACCOUNT_NUMBER"],
    }
    payload.update(overrides)
    return payload


def valid_correction_result(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": "1.0",
        "conversation_id": "C0001",
        "utterance_id": 17,
        "tuned_text": "[PERSON] 씨, 지금 [ACCOUNT_NUMBER] 계좌로 송금하세요.",
        "is_tuned": True,
        "has_unclear": False,
        "unclear_segments": [],
    }
    payload.update(overrides)
    return payload


class MaskedTranscriptTests(unittest.TestCase):
    def test_accepts_the_versioned_masked_contract(self) -> None:
        transcript = MaskedTranscript.from_dict(valid_masked_transcript())

        self.assertEqual("C0001", transcript.conversation_id)
        self.assertEqual(17, transcript.utterance_id)
        self.assertEqual(
            ("PERSON", "ACCOUNT_NUMBER"), transcript.masked_types
        )
        self.assertEqual(valid_masked_transcript(), transcript.to_dict())

    def test_rejects_raw_text_at_the_server_boundary(self) -> None:
        payload = valid_masked_transcript(raw_text="홍길동 123-456-789012")

        with self.assertRaisesRegex(ContractError, "raw_text"):
            MaskedTranscript.from_dict(payload)

    def test_rejects_unsupported_schema_versions(self) -> None:
        with self.assertRaisesRegex(ContractError, "schema_version"):
            MaskedTranscript.from_dict(
                valid_masked_transcript(schema_version="2.0")
            )

    def test_rejects_masked_types_that_do_not_match_the_text(self) -> None:
        with self.assertRaisesRegex(ContractError, "exactly match"):
            MaskedTranscript.from_dict(
                valid_masked_transcript(masked_types=["PERSON"])
            )

    def test_rejects_unknown_masking_tokens(self) -> None:
        with self.assertRaisesRegex(ContractError, "EMAIL"):
            MaskedTranscript.from_dict(
                valid_masked_transcript(
                    masked_text="[PERSON]의 [EMAIL]",
                    masked_types=["PERSON", "EMAIL"],
                )
            )

    def test_rejects_a_legacy_korean_masking_token(self) -> None:
        with self.assertRaisesRegex(ContractError, r"\[이름\]"):
            MaskedTranscript.from_dict(
                {
                    "schema_version": "1.0",
                    "conversation_id": "C0001",
                    "utterance_id": 17,
                    "masked_text": "[이름] 씨에게 연락하세요.",
                    "has_masked_data": False,
                    "masked_types": [],
                }
            )

    def test_rejects_inconsistent_has_masked_data(self) -> None:
        with self.assertRaisesRegex(ContractError, "has_masked_data"):
            MaskedTranscript.from_dict(
                valid_masked_transcript(has_masked_data=False)
            )


class CorrectionResultTests(unittest.TestCase):
    def test_accepts_the_versioned_correction_contract(self) -> None:
        result = CorrectionResult.from_dict(valid_correction_result())

        self.assertEqual("C0001", result.conversation_id)
        self.assertTrue(result.is_tuned)
        self.assertEqual(valid_correction_result(), result.to_dict())

    def test_accepts_matching_unclear_text_and_segments(self) -> None:
        result = CorrectionResult.from_dict(
            valid_correction_result(
                tuned_text="[PERSON] 씨 [불명확] 계좌로 송금하세요.",
                has_unclear=True,
                unclear_segments=["지금 그..."],
            )
        )

        self.assertTrue(result.has_unclear)
        self.assertEqual(("지금 그...",), result.unclear_segments)

    def test_rejects_inconsistent_unclear_metadata(self) -> None:
        with self.assertRaisesRegex(ContractError, "unclear_segments"):
            CorrectionResult.from_dict(
                valid_correction_result(
                    tuned_text="[PERSON] 씨 [불명확] 계좌로 송금하세요.",
                    has_unclear=False,
                )
            )

    def test_direct_construction_cannot_bypass_validation(self) -> None:
        with self.assertRaisesRegex(ContractError, "conversation_id"):
            CorrectionResult(
                schema_version="1.0",
                conversation_id="",
                utterance_id=17,
                tuned_text="정상 문장입니다.",
                is_tuned=True,
                has_unclear=False,
                unclear_segments=(),
            )

    def test_rejects_a_changed_masking_token(self) -> None:
        with self.assertRaisesRegex(ContractError, "preserve"):
            validate_masking_token_preservation(
                "[PERSON] 씨 [ACCOUNT_NUMBER] 계좌",
                "[PERSON] 씨 [PHONE_NUMBER] 계좌",
            )

    def test_rejects_reordered_masking_tokens(self) -> None:
        with self.assertRaisesRegex(ContractError, "original order"):
            validate_masking_token_preservation(
                "[PERSON] 씨 [ACCOUNT_NUMBER] 계좌",
                "[ACCOUNT_NUMBER] 계좌의 [PERSON] 씨",
            )

    def test_accepts_preserved_repeated_masking_tokens(self) -> None:
        validate_masking_token_preservation(
            "[PERSON]이 [PERSON]에게 연락했습니다.",
            "[PERSON]이 [PERSON]에게 연락했습니다.",
        )

    def test_validates_a_correction_against_its_input(self) -> None:
        transcript = MaskedTranscript.from_dict(valid_masked_transcript())
        result = CorrectionResult.from_dict(valid_correction_result())

        validate_correction_against_input(transcript, result)

    def test_rejects_a_result_for_another_conversation(self) -> None:
        transcript = MaskedTranscript.from_dict(valid_masked_transcript())
        result = CorrectionResult.from_dict(
            valid_correction_result(conversation_id="C0002")
        )

        with self.assertRaisesRegex(ContractError, "conversation_id"):
            validate_correction_against_input(transcript, result)

    def test_rejects_an_incorrect_is_tuned_value(self) -> None:
        payload = valid_masked_transcript()
        transcript = MaskedTranscript.from_dict(payload)
        result = CorrectionResult.from_dict(
            valid_correction_result(
                tuned_text=payload["masked_text"],
                is_tuned=True,
            )
        )

        with self.assertRaisesRegex(ContractError, "is_tuned"):
            validate_correction_against_input(transcript, result)

    def test_rejects_an_unclear_segment_not_found_in_the_input(self) -> None:
        transcript = MaskedTranscript.from_dict(valid_masked_transcript())
        result = CorrectionResult.from_dict(
            valid_correction_result(
                tuned_text=(
                    "[PERSON] 씨 [불명확] [ACCOUNT_NUMBER] 계좌로 송금하세요."
                ),
                has_unclear=True,
                unclear_segments=["입력에 없는 문장"],
            )
        )

        with self.assertRaisesRegex(ContractError, "original order"):
            validate_correction_against_input(transcript, result)

    def test_rejects_an_unclear_segment_left_in_the_output(self) -> None:
        transcript = MaskedTranscript.from_dict(
            valid_masked_transcript(
                masked_text=(
                    "[PERSON] 씨 지금 그... [ACCOUNT_NUMBER] 계좌로 송금하세요."
                )
            )
        )
        result = CorrectionResult.from_dict(
            valid_correction_result(
                tuned_text=(
                    "[PERSON] 씨 지금 그... [ACCOUNT_NUMBER] 계좌로 "
                    "송금하세요. [불명확]"
                ),
                has_unclear=True,
                unclear_segments=["지금 그..."],
            )
        )

        with self.assertRaisesRegex(ContractError, "must be removed"):
            validate_correction_against_input(transcript, result)


if __name__ == "__main__":
    unittest.main()
