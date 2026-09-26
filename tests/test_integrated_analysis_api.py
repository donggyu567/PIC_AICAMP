"""실제 AI·OpenAI 호출 없이 보정 엔진부터 저장까지 통합 검증한다."""

import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import app
from backend.services import analysis_service
from backend.services.ai_service import RiskModelScores
from backend.services.risk_service import ALLOWED_RISK_TYPES
from backend.stores.analysis_file_store import AnalysisFileStore
from models.llm_correction import CorrectionEngine


def utterance(number=1, conversation_id="pipeline-test"):
    return {
        "schema_version": "1.0",
        "conversation_id": conversation_id,
        "utterance_id": number,
        "masked_text": f"문장 {number}",
        "has_masked_data": False,
        "masked_types": [],
    }


class StubCorrectionClient:
    def __init__(self):
        self.calls = 0
        self.fail = False

    def complete(self, *, system_prompt, user_prompt):
        self.calls += 1
        if self.fail:
            raise RuntimeError("private provider detail")
        text = json.loads(user_prompt.splitlines()[-1])["masked_text"]
        return json.dumps({"tuned_text": text + ".", "unclear_segments": []})


class StubRiskAnalyzer:
    model_version = "test-risk-v1"

    def __init__(self):
        self.inputs = []
        self.fail = False
        self.invalid_result = None

    def analyze(self, model_input):
        self.inputs.append(model_input)
        if self.fail:
            raise TimeoutError("private inference detail")
        if self.invalid_result is not None:
            return self.invalid_result
        return RiskModelScores(
            is_phishing_score=0.55,
            type_scores={name: 0.0 for name in ALLOWED_RISK_TYPES},
            detected_types=[],
        )


class IntegratedAnalysisApiTests(unittest.TestCase):
    path = "/api/v1/utterances/analyze"
    retry_path = "/api/v1/utterances/analyze/retry"

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.store = AnalysisFileStore(Path(directory.name))
        self.provider = StubCorrectionClient()
        self.analyzer = StubRiskAnalyzer()
        for patcher in (
            patch.object(analysis_service, "analysis_store", self.store),
            patch.object(app.state, "risk_analyzer", self.analyzer, create=True),
            patch(
                "backend.services.pipeline_service.get_correction_engine",
                return_value=CorrectionEngine(self.provider),
            ),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def test_unconfigured_ai_fails_before_correction_and_storage(self):
        with patch.object(app.state, "risk_analyzer", None):
            response = self.client.post(self.path, json=utterance())
        self.assertEqual(503, response.status_code)
        self.assertEqual(0, self.provider.calls)
        self.assertEqual([], list(self.store.root.iterdir()))

    def test_correction_ai_calculation_and_persistence_are_connected(self):
        first = self.client.post(self.path, json=utterance())
        second = self.client.post(self.path, json=utterance(2))
        self.assertEqual(200, first.status_code)
        self.assertEqual(200, second.status_code)
        self.assertEqual("문장 1.", first.json()["current_text"])
        self.assertAlmostEqual(55.0, first.json()["cumulative_risk_score"])
        self.assertAlmostEqual(73.75, second.json()["cumulative_risk_score"])
        self.assertEqual((), self.analyzer.inputs[0].history_texts)
        self.assertEqual(("문장 1.",), self.analyzer.inputs[1].history_texts)
        self.assertEqual("문장 2.", self.analyzer.inputs[1].current_text)
        stored = self.store.load("pipeline-test").records[-1]
        self.assertEqual("test-risk-v1", stored.model_result.model_version)
        self.assertEqual(second.json(), stored.response.model_dump())

    def test_last_five_contexts_restore_after_restart_and_isolate_calls(self):
        for number in range(1, 8):
            self.assertEqual(200, self.client.post(self.path, json=utterance(number)).status_code)
        self.assertEqual(
            tuple(f"문장 {number}." for number in range(2, 7)),
            self.analyzer.inputs[-1].history_texts,
        )
        with patch.object(analysis_service, "analysis_store", AnalysisFileStore(self.store.root)):
            self.assertEqual(200, self.client.post(self.path, json=utterance(8)).status_code)
        self.assertEqual(
            tuple(f"문장 {number}." for number in range(3, 8)),
            self.analyzer.inputs[-1].history_texts,
        )
        self.client.post(self.path, json=utterance(conversation_id="another-call"))
        self.assertEqual((), self.analyzer.inputs[-1].history_texts)

    def test_invalid_masking_order_and_duplicates_do_not_call_models(self):
        invalid = {**utterance(), "masked_text": "[PERSON]님"}
        self.assertEqual(422, self.client.post(self.path, json=invalid).status_code)
        self.assertEqual(409, self.client.post(self.path, json=utterance(2)).status_code)
        self.assertEqual(0, self.provider.calls)
        self.client.post(self.path, json=utterance())
        self.assertEqual(409, self.client.post(self.path, json=utterance()).status_code)
        self.assertEqual(409, self.client.post(self.path, json=utterance(3)).status_code)
        self.assertEqual(1, self.provider.calls)
        self.assertEqual(1, len(self.analyzer.inputs))

    def test_correction_failure_does_not_advance_sequence(self):
        self.provider.fail = True
        response = self.client.post(self.path, json=utterance())
        self.assertEqual(502, response.status_code)
        self.assertNotIn("private provider detail", response.text)
        self.assertEqual([], self.analyzer.inputs)
        self.assertEqual([], self.store.get_history("pipeline-test"))
        self.provider.fail = False
        self.assertEqual(200, self.client.post(self.path, json=utterance()).status_code)

    def test_ai_failure_blocks_then_retry_reuses_correction_and_context(self):
        self.client.post(self.path, json=utterance())
        self.analyzer.fail = True
        with self.assertLogs("backend.services.pipeline_service", level="WARNING") as logged:
            failed = self.client.post(self.path, json=utterance(2))
        self.assertNotIn("private inference detail", " ".join(logged.output))
        self.assertEqual(200, failed.status_code)
        self.assertEqual("error", failed.json()["analysis_status"])
        self.assertIsNone(failed.json()["cumulative_risk_score"])
        self.assertEqual(409, self.client.post(self.path, json=utterance(3)).status_code)
        self.assertEqual(2, self.provider.calls)
        self.assertEqual(2, len(self.analyzer.inputs))
        self.analyzer.fail = False
        with patch.object(analysis_service, "analysis_store", AnalysisFileStore(self.store.root)):
            recovered = self.client.post(
                self.retry_path, json={"conversation_id": "pipeline-test", "utterance_id": 2},
            )
        self.assertEqual(200, recovered.status_code)
        self.assertAlmostEqual(73.75, recovered.json()["cumulative_risk_score"])
        self.assertEqual(2, self.provider.calls)
        self.assertEqual(self.analyzer.inputs[1], self.analyzer.inputs[2])
        self.assertEqual(1, len(self.store.load("pipeline-test").records[-1].previous_attempts))
        self.assertEqual(200, self.client.post(self.path, json=utterance(3)).status_code)

    def test_invalid_ai_output_is_stored_as_error_not_as_safe_score(self):
        base = {
            "is_phishing_score": 0.55,
            "type_scores": {name: 0.0 for name in ALLOWED_RISK_TYPES},
            "detected_types": [],
        }
        invalid = [
            RiskModelScores.model_construct(**{**base, "is_phishing_score": 55.0}),
            RiskModelScores.model_construct(**{**base, "is_phishing_score": float("nan")}),
            RiskModelScores.model_construct(**{**base, "type_scores": {}}),
            RiskModelScores.model_construct(**{**base, "detected_types": ["secrecy", "secrecy"]}),
            {"unexpected": "shape"},
        ]
        for index, result in enumerate(invalid):
            with self.subTest(index=index):
                self.analyzer.invalid_result = result
                with self.assertLogs("backend.services.pipeline_service", level="WARNING"):
                    response = self.client.post(
                        self.path, json=utterance(conversation_id=f"invalid-{index}"),
                    )
                self.assertEqual(200, response.status_code)
                self.assertEqual("error", response.json()["analysis_status"])
                self.assertIsNone(response.json()["current_risk_score"])

    def test_storage_failure_keeps_sequence_retryable(self):
        with patch("backend.stores.analysis_file_store.os.replace", side_effect=OSError("disk")):
            response = self.client.post(self.path, json=utterance())
        self.assertEqual(503, response.status_code)
        self.assertEqual([], self.store.get_history("pipeline-test"))
        self.assertEqual(200, self.client.post(self.path, json=utterance()).status_code)

    def test_retry_checks_target_before_ai_and_does_not_recorrect(self):
        retry = {"conversation_id": "pipeline-test", "utterance_id": 1}
        self.assertEqual(404, self.client.post(self.retry_path, json=retry).status_code)
        self.client.post(self.path, json=utterance())
        self.assertEqual(409, self.client.post(self.retry_path, json=retry).status_code)
        self.assertEqual(1, self.provider.calls)
        self.assertEqual(1, len(self.analyzer.inputs))

    def test_concurrent_duplicate_calls_run_models_once(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            statuses = list(pool.map(
                lambda _: self.client.post(self.path, json=utterance()).status_code,
                range(4),
            ))
        self.assertEqual([200, 409, 409, 409], sorted(statuses))
        self.assertEqual(1, self.provider.calls)
        self.assertEqual(1, len(self.analyzer.inputs))


if __name__ == "__main__":
    unittest.main()
