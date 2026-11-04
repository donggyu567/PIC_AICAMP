"""Approval extraction must reject unsigned decisions and preserve context."""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "dataset/scripts"))
import finalize_pilot_review as finalize
import prepare_pilot_review as review
import restore_pilot as source


class ApprovalTests(unittest.TestCase):
    def setUp(self):
        self.baseline = review.expected_rows()
        self.rows = copy.deepcopy(self.baseline)

    def approve(self, row):
        for name in review.REVIEWERS:
            row[f"검수_결과_{name}"] = "승인"
            row[f"검수_일시_{name}"] = "2026-11-05 14:00 KST"
        row["최종_합의_결과"] = "승인"
        row["최종_합의_일시"] = "2026-11-05 14:30 KST"

    def test_unreviewed_file_exports_nothing(self):
        counts, accepted, issues, errors, changes = finalize.analyze(self.rows, self.baseline)
        self.assertEqual(counts["review_incomplete"], 136)
        self.assertEqual(counts["both_approved"], 0)
        self.assertEqual(len(issues), 136)
        self.assertFalse(accepted or errors or changes)

    def test_both_approvals_still_need_final_and_dates(self):
        self.approve(self.rows[0])
        self.rows[0]["unexpected_column"] = "unexpected column"
        self.approve(self.rows[1])
        self.rows[1]["최종_합의_결과"] = "미승인"
        self.approve(self.rows[2])
        self.rows[2]["검수_일시_임정윤"] = ""
        self.assertFalse(finalize.analyze(self.rows, self.baseline)[1])

    def test_comments_and_source_mutation_not_automatically_applied(self):
        self.approve(self.rows[0])
        self.rows[0]["합의_수정안"] = 'labels / ["money_transfer"] / 재검수 필요'
        self.approve(self.rows[1])
        self.rows[1]["피싱_여부"] = "true"
        counts, accepted, issues, _, _ = finalize.analyze(self.rows, self.baseline)
        self.assertFalse(accepted)
        self.assertEqual(counts["label_proposal_rows"], 1)
        self.assertIn("FREE_TEXT_REQUIRES_EXPLICIT_RESOLUTION", issues[0]["reasons"])
        self.assertIn("SOURCE_COLUMNS_CHANGED", issues[1]["reasons"])

    def test_partial_conversation_cannot_leak_to_context(self):
        canonical, _ = source.restore()
        accepted = {row["발화_ID"] for row in self.rows[:10]}
        candidates, usable, contexts, windows = finalize.select_conversations(canonical, accepted)
        self.assertEqual(len(usable), 1)
        self.assertEqual(len(windows), 10)
        self.assertLessEqual(max(len(w["previous_utterance_ids"]) for w in windows), 5)
        accepted.remove(self.rows[3]["발화_ID"])
        candidates, usable, contexts, windows = finalize.select_conversations(canonical, accepted)
        self.assertEqual(len(candidates), 1)
        self.assertFalse(usable or windows)
        self.assertTrue(contexts[0]["targets_with_excluded_previous_context"])

    def test_label_audit_preserves_original(self):
        self.approve(self.rows[0])
        _, accepted, _, _, changes = finalize.analyze(self.rows, self.baseline)
        self.assertEqual(accepted, {self.rows[0]["발화_ID"]})
        self.assertEqual(changes[0]["original_labels"], changes[0]["approved_labels"])
        self.assertEqual(changes[0]["changed_fields"], [])


if __name__ == "__main__":
    unittest.main()
