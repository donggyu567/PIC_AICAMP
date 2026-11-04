"""Protect source columns and the two-person approval prerequisite."""
import csv
import importlib.util
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "dataset/scripts/prepare_pilot_review.py"
SPEC = importlib.util.spec_from_file_location("prepare_pilot_review", SCRIPT)
review = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(review)


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "review.csv"
        self.rows = review.expected_rows()

    def save(self):
        with self.path.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=review.COLUMNS)
            writer.writeheader()
            writer.writerows(self.rows)

    def test_all_rows_unapproved_and_requested_flags(self):
        self.save()
        report = review.validate(self.path, review.expected_rows())
        self.assertEqual(report["rows"], 136)
        self.assertEqual(report["final_results"], {"미승인": 136})
        for row in self.rows:
            number = int(row["대화_ID"].split("-")[-1])
            uid = int(row["발화_번호"])
            if number in {7, 11} or (number, uid) in {(5, 7), (6, 4), (9, 5), (10, 5)}:
                self.assertEqual(row["검토_필요"], "예")
                self.assertTrue(row["검토_사유"])

    def test_source_changes_rejected(self):
        self.rows[0]["발화_내용"] += "수정"
        self.save()
        with self.assertRaisesRegex(ValueError, "Source/annotation column changed"):
            review.validate(self.path, review.expected_rows())

    def test_single_reviewer_cannot_finalize(self):
        row = self.rows[0]
        row["검수_결과_김해린"] = "승인"
        row["검수_일시_김해린"] = "2026-11-05 14:00 KST"
        row["최종_합의_결과"] = "승인"
        row["최종_합의_일시"] = "2026-11-05 15:00 KST"
        self.save()
        with self.assertRaisesRegex(ValueError, "Both reviewers must approve"):
            review.validate(self.path, review.expected_rows())

    def test_sorting_and_reviewer_input_preserved(self):
        self.rows[0]["검수_결과_임정윤"] = "수정요청"
        self.rows[0]["검수_일시_임정윤"] = "2026-11-05 14:00 KST"
        self.rows[0]["수정_의견_임정윤"] = '피싱 여부 / false / 문맥 확인, "재검수"\n다음 줄 의견'
        self.rows.reverse()
        self.save()
        before = self.path.read_bytes()
        report = review.validate(self.path, review.expected_rows())
        self.assertEqual(report["reviewer_results"]["임정윤"]["수정요청"], 1)
        self.assertEqual(self.path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
