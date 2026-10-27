"""A conversation pass alone cannot authorize training rows."""

import unittest
from unittest.mock import patch

from risk_speech_ai.prepare_training_inputs import APPROVAL_SCOPE, prepare, prepare_team_approved, row_hash


class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.row = {"conversation_id": "P0030", "utterance_id": 1,
                    "text": "[PERSON] 계좌로 송금하세요.", "is_phishing": True,
                    "labels": ["money_transfer"]}
        self.manifest = [{"id": "P0030", "source": "S031", "review": "통과",
                          "path": "dataset/03. masked/phishing/P0030.jsonl",
                          "expected_utterances": 1}]
        self.approval = {"conversation_id": "P0030", "utterance_id": 1,
                         "scope": APPROVAL_SCOPE, "data_commit": "commit-id",
                         "reviewer": "reviewer", "evidence_url": "https://example.com/review/1",
                         "row_sha256": row_hash(self.row), "masking_verified": True,
                         "license_confirmed": True, "label_status": "reviewed"}
        self.correction = {"conversation_id": "P0030", "utterance_id": 1,
                           "schema_version": "1.0", "masked_text": self.row["text"],
                           "source_row_sha256": row_hash(self.row),
                           "validation_status": "passed", "validation_source": "saved backend result",
                           "tuned_text": self.row["text"], "is_tuned": False,
                           "has_unclear": False, "unclear_segments": []}

    def run_prepare(self, approvals, corrections):
        with patch("risk_speech_ai.prepare_training_inputs._source_rows", return_value=[self.row]):
            return prepare(self.manifest, approvals, corrections, "commit-id")

    def test_sheet_pass_without_utterance_evidence_stays_pending(self):
        labels, tuned, pending = self.run_prepare([], [])
        self.assertEqual(([], []), (labels, tuned))
        self.assertEqual("utterance_approval_missing", pending[0]["reason"])

    def test_exact_approval_and_validated_backend_result_connect(self):
        labels, tuned, pending = self.run_prepare([self.approval], [self.correction])
        self.assertFalse(pending)
        self.assertEqual("reviewed", labels[0]["label_status"])
        self.assertEqual(self.row["text"], tuned[0]["tuned_text"])

    def test_wrong_scope_or_mask_token_cannot_pass(self):
        approval = dict(self.approval, scope="conversation_pass")
        self.assertEqual("approval_scope_or_version_unverified",
                         self.run_prepare([approval], [self.correction])[2][0]["reason"])
        correction = dict(self.correction, tuned_text="송금하세요.", is_tuned=True)
        self.assertEqual("backend_mask_contract_mismatch",
                         self.run_prepare([self.approval], [correction])[2][0]["reason"])

    def test_true_without_type_needs_explicit_out_of_taxonomy(self):
        self.row["labels"] = []
        approval = dict(self.approval, row_sha256=row_hash(self.row))
        correction = dict(self.correction, source_row_sha256=row_hash(self.row))
        self.assertEqual("risk_type_unresolved",
                         self.run_prepare([approval], [correction])[2][0]["reason"])
        approval["label_status"] = "out_of_taxonomy"
        self.assertEqual(1, len(self.run_prepare([approval], [correction])[0]))

    def test_team_training_use_does_not_claim_human_review_or_llm_correction(self):
        with patch("risk_speech_ai.prepare_training_inputs._source_rows", return_value=[self.row]):
            labels, tuned, pending = prepare_team_approved(self.manifest, "commit-id")
        self.assertFalse(pending)
        self.assertEqual("approved_for_training", labels[0]["label_status"])
        self.assertEqual(self.manifest[0]["review"], labels[0]["human_review_status"])
        self.assertEqual("masked_source_text_no_llm_correction", tuned[0]["preprocessing"])

    def test_team_training_use_excludes_unresolved_risk_type(self):
        self.row["labels"] = []
        with patch("risk_speech_ai.prepare_training_inputs._source_rows", return_value=[self.row]):
            labels, tuned, pending = prepare_team_approved(self.manifest, "commit-id")
        self.assertFalse(labels or tuned)
        self.assertEqual("risk_type_unresolved", pending[0]["reason"])


if __name__ == "__main__":
    unittest.main()
