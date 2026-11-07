import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient
from openai import OpenAIError

from backend.stores.analysis_file_store import AnalysisFileStore
from server.main import app
from server.security.access import authenticated_device
from tests.api_helpers import StubRiskAnalyzer, utterance


def completion(text="문장 1.", evidence_ids=(1,)):
    return SimpleNamespace(
        status="completed", output=[], usage=None, service_tier="priority",
        output_text=json.dumps({
            "corrected_text": text,
            "context_judgment": {
                "assessment": "suspicious",
                "reason": "문맥에서 이체 요구가 확인됩니다.",
                "evidence_utterance_ids": list(evidence_ids),
                "risk_types": ["money_transfer"],
            },
        }),
    )


class AnalysisApiTests(unittest.TestCase):
    def setUp(self):
        app.dependency_overrides[authenticated_device] = lambda: "test-device"
        self.addCleanup(app.dependency_overrides.pop, authenticated_device, None)
        self.enterContext(patch("server.analysis.router.require_conversation_owner"))
        self.enterContext(patch("server.analysis.lifecycle_router.require_conversation_owner"))
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.store = AnalysisFileStore(Path(directory.name))
        self.enterContext(patch("backend.services.analysis_service.analysis_store", self.store))
        self.enterContext(patch.dict("os.environ", {
            "PIC_AI_MODE": "disabled", "PIC_CONTEXT_MODEL": "test-context-model",
            "OPENAI_API_KEY": "test-key",
        }))
        self.openai = self.enterContext(patch("server.analysis.context_service.OpenAI"))
        self.complete = self.openai.return_value.responses.create
        self.complete.return_value = completion()
        self.legacy_correction = self.enterContext(patch(
            "backend.services.pipeline_service.get_correction_engine",
            side_effect=AssertionError("new server must not call correction twice"),
        ))
        self.addCleanup(self.openai.return_value.close.assert_called_once)
        self.client = self.enterContext(TestClient(app))
        self.analyzer = StubRiskAnalyzer()
        app.state.risk_analyzer = self.analyzer
        self.payload = utterance() | {"masking_status": "succeeded"}

    def post(self, **changes):
        return self.client.post("/api/v1/utterances/analyze", json=self.payload | changes)

    def test_android_extra_tokens_reach_analysis_without_unmasking(self):
        text = "[EMAIL] 및 [OTP]를 알려주세요."
        self.complete.return_value = completion(text)
        response = self.post(masked_text=text, has_masked_data=True, masked_types=["EMAIL", "OTP"])
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["correction_status"], "ok")
        self.assertEqual(self.analyzer.inputs[0].current_text, text)

    def test_single_call_precedes_ai_and_corrected_text_is_saved(self):
        def combined(**kwargs):
            self.assertEqual(self.analyzer.inputs, [])
            return completion("문장 1.")
        self.complete.side_effect = combined
        result = self.post()
        self.assertEqual(result.status_code, 200, result.text)
        data = result.json()
        self.assertEqual(data["correction_status"], "ok")
        self.assertEqual(data["analysis_status"], "ok")
        self.assertEqual(data["context_judgment"]["status"], "ok")
        self.assertEqual(data["current_text"], "문장 1.")
        self.assertEqual(self.analyzer.inputs[0].current_text, "문장 1.")
        self.complete.assert_called_once()
        self.legacy_correction.assert_not_called()
        self.assertIn("llm_preparation;dur=", result.headers["server-timing"])
        self.assertEqual(self.store.load("pipeline-test").records[0].response.model_dump(mode="json"), data)
        self.assertEqual(self.post().status_code, 409)
        self.complete.assert_called_once()

    def test_ai_retry_preserves_successful_llm_without_another_call(self):
        self.analyzer.fail = True
        failed = self.post()
        self.assertEqual(failed.status_code, 200, failed.text)
        self.assertEqual(failed.json()["analysis_status"], "error")
        self.assertEqual(failed.json()["context_judgment"]["status"], "ok")
        self.analyzer.fail = False
        retried = self.client.post("/api/v1/utterances/analyze/retry", json={
            "conversation_id": "pipeline-test", "utterance_id": 1,
        })
        self.assertEqual(retried.status_code, 200, retried.text)
        self.assertEqual(retried.json()["analysis_status"], "ok")
        self.assertEqual(retried.json()["correction_status"], "ok")
        self.assertEqual(retried.json()["context_judgment"], failed.json()["context_judgment"])
        self.assertEqual(self.analyzer.inputs[0].current_text, self.analyzer.inputs[1].current_text)
        self.complete.assert_called_once()
        record = self.store.load("pipeline-test").records[0]
        self.assertEqual(record.response.model_dump(mode="json"), retried.json())
        self.assertEqual(record.previous_attempts[0].response.analysis_status, "error")

    def test_masking_failure_and_token_mismatch_never_reach_llm(self):
        for change in (
            {"masking_status": "failed"},
            {"masked_text": "[PHONE_NUMBER]", "masked_types": [], "has_masked_data": False},
        ):
            self.assertEqual(self.post(**change).status_code, 422)
        self.complete.assert_not_called()
        self.assertEqual(self.analyzer.inputs, [])

    def test_context_uses_history_without_ai_scores(self):
        second_text = "[ACCOUNT_NUMBER]로 이체하세요."
        self.complete.side_effect = [completion(), completion(second_text, (1, 2))]
        first = self.post()
        second = self.post(utterance_id=2, masked_text=second_text,
                           has_masked_data=True, masked_types=["ACCOUNT_NUMBER"])
        self.assertEqual(second.status_code, 200, second.text)
        data = second.json()
        self.assertEqual(data["context_judgment"]["result"]["evidence_utterance_ids"], [1, 2])
        self.assertAlmostEqual(data["current_risk_score"], 55.0)
        request = self.complete.call_args.kwargs
        context = json.loads(request["input"])
        self.assertEqual(context["utterances"], [
            {"utterance_id": 1, "text": first.json()["current_text"]},
            {"utterance_id": 2, "text": second_text},
        ])
        self.assertNotIn("cumulative_risk_score", context)
        self.assertNotIn("current_risk_score", context)
        self.assertNotIn("conversation_id", context)
        self.assertEqual(request["truncation"], "disabled")
        self.assertFalse(request["store"])
        self.assertEqual(self.complete.call_count, 2)
        self.openai.assert_called_once_with(timeout=10.0, max_retries=0)
        self.assertEqual(request["reasoning"], {"effort": "low"})
        self.assertEqual(request["service_tier"], "fast")
        self.assertEqual(request["max_output_tokens"], 2048)
        self.assertEqual(self.store.load("pipeline-test").records[-1].response.model_dump(mode="json"), data)

    def test_provider_failure_falls_back_without_stale_judgment(self):
        self.complete.side_effect = [completion(), OpenAIError("private provider detail")]
        self.assertEqual(self.post().json()["context_judgment"]["status"], "ok")
        with self.assertLogs("server.analysis.context_service", level="WARNING") as logs:
            failed = self.post(utterance_id=2)
        self.assertEqual(failed.status_code, 200, failed.text)
        data = failed.json()
        self.assertEqual(data["analysis_status"], "ok")
        self.assertEqual(data["correction_status"], "fallback")
        self.assertEqual(data["current_text"], self.payload["masked_text"])
        self.assertEqual(data["context_judgment"], {
            "status": "error", "model": "test-context-model", "result": None,
        })
        self.assertNotIn("private provider detail", failed.text + "".join(logs.output))

    def test_invalid_tokens_evidence_and_refusal_discard_combined_output(self):
        masked = "[ACCOUNT_NUMBER]로 이체하지 마세요."
        refused = completion(masked)
        refused.output = [SimpleNamespace(type="message", content=[SimpleNamespace(type="refusal")])]
        cases = [completion("[PHONE_NUMBER]로 이체하지 마세요."),
                 completion(masked, (99,)), refused]
        for index, value in enumerate(cases):
            with self.subTest(index=index), self.assertLogs("server.analysis.context_service", level="WARNING"):
                self.complete.return_value = value
                result = self.post(conversation_id=f"invalid-{index}", masked_text=masked,
                                   has_masked_data=True, masked_types=["ACCOUNT_NUMBER"])
            self.assertEqual(result.status_code, 200, result.text)
            self.assertEqual(result.json()["analysis_status"], "ok")
            self.assertEqual(result.json()["correction_status"], "fallback")
            self.assertEqual(result.json()["context_judgment"]["status"], "error")
            self.assertEqual(self.analyzer.inputs[-1].current_text, masked)

    def test_missing_model_skips_llm_and_uses_masked_input(self):
        self.enterContext(patch.dict("os.environ", {"PIC_CONTEXT_MODEL": ""}))
        result = self.post()
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()["correction_status"], "fallback")
        self.assertEqual(result.json()["context_judgment"]["status"], "not_run")
        self.assertEqual(self.analyzer.inputs[0].current_text, self.payload["masked_text"])
        self.complete.assert_not_called()


if __name__ == "__main__":
    unittest.main()
