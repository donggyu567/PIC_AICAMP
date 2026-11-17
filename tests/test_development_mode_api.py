"""AI 시작 모드와 개발 분석기 연결을 다운로드·체크포인트 없이 검증한다."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.lifespan import resolve_ai_mode
from backend.main import app
from backend.services import analysis_service
from backend.services.koelectra_analyzer import KoElectraRiskAnalyzer
from backend.services.risk_service import ALLOWED_RISK_TYPES
from backend.stores.analysis_file_store import AnalysisFileStore
from models.llm_correction import CorrectionEngine
from models.warning_manager.warning_manager import DefaultWarningManager
from risk_speech_ai.inference import InferenceOutput
from tests.api_helpers import StubCorrectionClient, StubRiskAnalyzer, utterance


def ai_environment(**settings):
    """개발자의 로컬 AI 설정이 테스트 결과에 영향을 주지 않도록 격리한다."""
    environment = {
        key: value for key, value in os.environ.items()
        if not key.startswith("PIC_AI_")
    }
    return patch.dict(os.environ, {**environment, **settings}, clear=True)


class FixedPredictor:
    """어댑터를 통과하는 고정 추론 결과. 모델 파일이나 네트워크를 사용하지 않는다."""

    def __init__(self):
        self.inputs = []
        self.fail = False

    def predict(self, inputs):
        self.inputs.extend(inputs)
        if self.fail:
            raise TimeoutError("private predictor detail")
        probabilities = {
            name: 0.8 if name == "money_transfer" else 0.0
            for name in ALLOWED_RISK_TYPES
        }
        return [InferenceOutput(
            risk_score=55.0,
            risk_probability=0.55,
            type_scores={name: 100 * value for name, value in probabilities.items()},
            type_probabilities=probabilities,
            detected_types=["money_transfer"],
        ) for _ in inputs]


class AiModeConfigurationTests(unittest.TestCase):
    def test_default_and_legacy_flags(self):
        for environment, expected in (
            ({}, "disabled"),
            ({"PIC_AI_ENABLED": "0"}, "disabled"),
            ({"PIC_AI_ENABLED": " 1 "}, "checkpoint"),
        ):
            with self.subTest(environment=environment), ai_environment(**environment):
                self.assertEqual(expected, resolve_ai_mode())

    def test_explicit_mode_takes_precedence_over_legacy_flag(self):
        for mode in ("disabled", "development", "checkpoint"):
            with self.subTest(mode=mode), ai_environment(
                PIC_AI_MODE=f" {mode} ", PIC_AI_ENABLED="invalid-legacy-value",
            ):
                self.assertEqual(mode, resolve_ai_mode())

    def test_invalid_modes_fail_instead_of_silently_disabling_ai(self):
        for mode in ("", "   ", "DEVELOPMENT", "dev", "1"):
            with self.subTest(mode=mode), ai_environment(PIC_AI_MODE=mode):
                with self.assertRaisesRegex(ValueError, "PIC_AI_MODE"):
                    resolve_ai_mode()
        with ai_environment(PIC_AI_ENABLED="yes"):
            with self.assertRaisesRegex(ValueError, "PIC_AI_ENABLED"):
                resolve_ai_mode()


class AiStartupTests(unittest.TestCase):
    def assert_cleared(self):
        self.assertIsNone(app.state.risk_analyzer)
        self.assertIsNone(app.state.warning_manager)
        self.assertEqual("disabled", app.state.ai_mode)

    def test_default_disabled_mode_does_not_import_ai_loaders(self):
        with ai_environment(), patch("builtins.__import__", wraps=__import__) as imports:
            with TestClient(app) as client:
                self.assertIsInstance(app.state.warning_manager, DefaultWarningManager)
                self.assertEqual({"status": "ok"}, client.get("/health").json())
                ready = client.get("/health/ready")
                self.assertEqual(503, ready.status_code)
                self.assertEqual({
                    "status": "not_ready",
                    "ai_ready": False,
                    "warning_ready": True,
                    "ai_mode": "disabled",
                    "model_version": None,
                }, ready.json())
                self.assertEqual(503, client.post(
                    "/api/v1/utterances/analyze", json=utterance(),
                ).status_code)
            imported_names = {call.args[0] for call in imports.call_args_list}
            self.assertNotIn("backend.services.ai_loader", imported_names)
            self.assertNotIn("backend.services.development_analyzer", imported_names)
        self.assert_cleared()

    def test_legacy_checkpoint_startup_still_uses_checkpoint_loader(self):
        analyzer = StubRiskAnalyzer()
        with (
            ai_environment(
                PIC_AI_ENABLED="1", PIC_AI_CHECKPOINT="team-model.pt",
                PIC_AI_MODEL_VERSION=analyzer.model_version,
            ),
            patch("backend.services.ai_loader.load_risk_analyzer", return_value=analyzer) as loader,
            TestClient(app) as client,
        ):
            loader.assert_called_once_with(
                "team-model.pt", model_version=analyzer.model_version, device="cpu",
            )
            ready = client.get("/health/ready")
            self.assertEqual(200, ready.status_code)
            self.assertEqual("checkpoint", ready.json()["ai_mode"])
            self.assertEqual(analyzer.model_version, ready.json()["model_version"])
        self.assert_cleared()

    def test_checkpoint_settings_are_required_only_for_checkpoint_mode(self):
        for settings, missing in (
            ({}, "PIC_AI_CHECKPOINT"),
            ({"PIC_AI_CHECKPOINT": "team-model.pt"}, "PIC_AI_MODEL_VERSION"),
        ):
            with self.subTest(missing=missing), ai_environment(PIC_AI_MODE="checkpoint", **settings):
                with self.assertRaisesRegex(ValueError, missing), TestClient(app):
                    self.fail("invalid checkpoint settings must prevent startup")
                self.assert_cleared()

    def test_invalid_mode_and_failed_model_load_clean_up_state(self):
        with ai_environment(PIC_AI_MODE="typo"):
            with self.assertRaisesRegex(ValueError, "PIC_AI_MODE"), TestClient(app):
                self.fail("invalid mode must prevent startup")
        self.assert_cleared()
        with (
            ai_environment(PIC_AI_MODE="development"),
            patch("backend.services.development_analyzer.load_development_analyzer",
                  side_effect=RuntimeError("model cache unavailable")),
        ):
            with self.assertRaisesRegex(RuntimeError, "model cache unavailable"), TestClient(app):
                self.fail("failed model load must prevent startup")
        self.assert_cleared()


class DevelopmentModeApiTests(unittest.TestCase):
    path = "/api/v1/utterances/analyze"
    conversation_id = "development-test"

    def setUp(self):
        directory = self.enterContext(tempfile.TemporaryDirectory())
        self.store = AnalysisFileStore(Path(directory))
        self.predictor = FixedPredictor()
        self.provider = StubCorrectionClient()
        self.enterContext(ai_environment(PIC_AI_MODE="development"))
        self.enterContext(patch.object(analysis_service, "analysis_store", self.store))
        self.constructor = self.enterContext(patch(
            "backend.services.development_analyzer.DevelopmentPredictor",
            return_value=self.predictor,
        ))
        self.enterContext(patch(
            "backend.services.ai_loader.load_risk_analyzer",
            side_effect=AssertionError("development mode must not read a checkpoint"),
        ))
        self.enterContext(patch(
            "backend.services.pipeline_service.get_correction_engine",
            return_value=CorrectionEngine(self.provider),
        ))
        self.client = self.enterContext(TestClient(app))

    def post_utterance(self, number):
        response = self.client.post(self.path, json=utterance(number, self.conversation_id))
        self.assertEqual(200, response.status_code, response.text)
        return response.json()

    def test_startup_uses_real_adapter_once_and_exposes_development_version(self):
        analyzer = app.state.risk_analyzer
        self.assertIsInstance(analyzer, KoElectraRiskAnalyzer)
        self.assertTrue(analyzer.model_version.startswith("development-untrained-"))
        for number in (1, 2):
            ready = self.client.get("/health/ready")
            self.assertEqual(200, ready.status_code)
            self.assertEqual({
                "status": "ready", "ai_ready": True, "warning_ready": True,
                "ai_mode": "development", "model_version": analyzer.model_version,
            }, ready.json())
            self.post_utterance(number)
            self.assertIs(analyzer, app.state.risk_analyzer)
        self.constructor.assert_called_once_with()

    def test_adapter_context_calculation_warning_and_persistence(self):
        first = self.post_utterance(1)
        second = self.post_utterance(2)
        self.assertAlmostEqual(55.0, first["current_risk_score"])
        self.assertAlmostEqual(73.75, second["cumulative_risk_score"])
        self.assertEqual("active", second["warning"]["status"])
        self.assertEqual("cumulative", second["warning"]["reason"])
        self.assertEqual([], self.predictor.inputs[0].history_texts)
        self.assertEqual(["문장 1."], self.predictor.inputs[1].history_texts)
        self.assertEqual("문장 2.", self.predictor.inputs[1].current_text)
        snapshot = self.store.load(self.conversation_id)
        self.assertEqual(2, len(snapshot.records))
        self.assertEqual(app.state.risk_analyzer.model_version,
                         snapshot.records[-1].model_result.model_version)
        self.assertEqual(second, snapshot.records[-1].response.model_dump())
        fetched = self.client.get("/api/v1/dev/model-results", params={
            "conversation_id": self.conversation_id,
        })
        self.assertEqual(200, fetched.status_code)
        self.assertEqual(second, fetched.json())

    def test_failure_retry_and_end_use_the_same_development_adapter(self):
        self.post_utterance(1)
        self.predictor.fail = True
        with self.assertLogs("backend.services.pipeline_service", level="WARNING"):
            failed = self.post_utterance(2)
        self.assertEqual("error", failed["analysis_status"])
        self.assertIsNone(failed["current_risk_score"])
        self.assertEqual(409, self.client.post(
            self.path, json=utterance(3, self.conversation_id),
        ).status_code)
        self.predictor.fail = False
        retry_body = {"conversation_id": self.conversation_id, "utterance_id": 2}
        recovered = self.client.post(self.path + "/retry", json=retry_body)
        self.assertEqual(200, recovered.status_code, recovered.text)
        self.assertAlmostEqual(73.75, recovered.json()["cumulative_risk_score"])
        self.assertEqual(2, self.provider.calls)
        self.assertEqual(self.predictor.inputs[1], self.predictor.inputs[2])
        self.assertEqual(1, len(self.store.load(self.conversation_id).records[-1].previous_attempts))
        ended = self.client.post("/api/v1/conversations/end", json={
            "conversation_id": self.conversation_id,
        })
        self.assertEqual(200, ended.status_code)
        self.assertEqual("ended", ended.json()["conversation_status"])
        self.assertEqual(409, self.client.post(
            self.path, json=utterance(3, self.conversation_id),
        ).status_code)
        self.assertEqual(409, self.client.post(self.path + "/retry", json=retry_body).status_code)
        self.assertEqual(3, len(self.predictor.inputs))
        self.assertEqual(2, self.provider.calls)


class DevelopmentInferenceTests(unittest.TestCase):
    def test_real_predictor_runs_tiny_torch_model_through_the_api(self):
        # 모델·토크나이저 자원 준비만 대체하고 predict/infer_batch/forward는 실제 실행한다.
        from tests.ai_helpers import SmallPairTokenizer, tiny_model

        model = tiny_model()
        tokenizer = SmallPairTokenizer()
        provider = StubCorrectionClient()
        with tempfile.TemporaryDirectory() as directory:
            store = AnalysisFileStore(Path(directory))
            with (
                ai_environment(PIC_AI_MODE="development"),
                patch.object(analysis_service, "analysis_store", store),
                patch("backend.services.development_analyzer.load_koelectra_tokenizer",
                      return_value=tokenizer) as tokenizer_loader,
                patch("backend.services.development_analyzer.RiskSpeechClassifier",
                      return_value=model) as model_loader,
                patch("transformers.ElectraModel.from_pretrained",
                      side_effect=AssertionError("this test must not download model files")),
                patch.object(model, "forward", wraps=model.forward) as forward,
                patch("backend.services.pipeline_service.get_correction_engine",
                      return_value=CorrectionEngine(provider)),
                TestClient(app) as client,
            ):
                version = app.state.risk_analyzer.model_version
                for number in (1, 2):
                    response = client.post(
                        "/api/v1/utterances/analyze",
                        json=utterance(number, "tiny-development-test"),
                    )
                    self.assertEqual(200, response.status_code, response.text)
                    body = response.json()
                    self.assertEqual("ok", body["analysis_status"])
                    self.assertGreaterEqual(body["current_risk_score"], 0.0)
                    self.assertLessEqual(body["current_risk_score"], 100.0)
                    self.assertGreaterEqual(body["cumulative_risk_score"], body["current_risk_score"])
                    self.assertIsNotNone(body["warning"])
                    snapshot = store.load("tiny-development-test")
                    self.assertEqual(version, snapshot.records[-1].model_result.model_version)
                    self.assertEqual(body, snapshot.records[-1].response.model_dump())
                self.assertEqual(2, forward.call_count)
                self.assertEqual(2, provider.calls)
                tokenizer_loader.assert_called_once_with()
                model_loader.assert_called_once_with()
                self.assertFalse(model.training)


if __name__ == "__main__":
    unittest.main()
