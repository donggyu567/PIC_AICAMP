import unittest

from backend.schemas import CalculationPreviewResponse, ContextJudgmentResult, ContextRiskJudgment
from server.analysis.risk_display import add_risk_display


def result(score, *, status="ok", context=None):
    return CalculationPreviewResponse(
        conversation_id="test", utterance_id=1, revision=0, sequence=1,
        analysis_status=status, current_text="안녕하세요",
        current_risk_score=score, cumulative_risk_score=score,
        type_scores=None, detected_types=None, calculation=None,
        context_judgment=context or ContextJudgmentResult(),
    )


class RiskDisplayTests(unittest.TestCase):
    def test_score_boundaries_use_unrounded_score(self):
        for score, expected in ((0, "normal"), (49.999, "normal"), (50, "caution"),
                                (69.999, "caution"), (70, "danger"), (100, "danger")):
            with self.subTest(score=score):
                self.assertEqual(expected, add_risk_display(result(score)).display.level)

    def test_context_attention_is_separate_from_ai_level(self):
        judgment = ContextRiskJudgment(assessment="suspicious", reason="이체 요구", evidence_utterance_ids=[1], risk_types=[])
        context = ContextJudgmentResult(status="ok", model="test", result=judgment)
        display = add_risk_display(result(10, context=context)).display
        self.assertEqual("normal", display.level)
        self.assertTrue(display.context_attention)
        self.assertIsNone(add_risk_display(result(10)).display.context_attention)
        self.assertEqual("unknown", add_risk_display(result(None, status="error", context=context)).display.level)
        for assessment, expected in (("no_clear_risk", False), ("insufficient_context", None)):
            judgment = ContextRiskJudgment(assessment=assessment, reason="결과", evidence_utterance_ids=[], risk_types=[])
            context = ContextJudgmentResult(status="ok", model="test", result=judgment)
            self.assertIs(add_risk_display(result(80, context=context)).display.context_attention, expected)


if __name__ == "__main__":
    unittest.main()
