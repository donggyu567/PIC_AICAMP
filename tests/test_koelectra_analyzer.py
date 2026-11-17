import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import Mock

from pydantic import ValidationError

from backend.services.ai_service import RiskModelInput
from backend.services.koelectra_analyzer import KoElectraRiskAnalyzer
from risk_speech_ai.inference import CheckpointInference, InferenceOutput
from risk_speech_ai.labels import LABELS


class KoElectraRiskAnalyzerTests(unittest.TestCase):
    def setUp(self):
        self.predictor = Mock(spec=CheckpointInference)
        self.analyzer = KoElectraRiskAnalyzer(
            self.predictor,
            model_version="test-model-v1",
        )
        self.model_input = RiskModelInput(
            current_text="안전계좌로 송금해주세요.",
            history_texts=("금융감독원입니다.",),
        )

        probabilities = {label: 0.1 for label in LABELS}
        probabilities["money_transfer"] = 0.9

        self.output = InferenceOutput(
            risk_score=82.0,
            risk_probability=0.82,
            type_scores={
                label: value * 100
                for label, value in probabilities.items()
            },
            type_probabilities=probabilities,
            detected_types=["money_transfer"],
        )
        self.predictor.predict.return_value = [self.output]

    def test_maps_input_and_uses_probabilities(self):
        result = self.analyzer.analyze(self.model_input)

        self.assertEqual(result.is_phishing_score, 0.82)
        self.assertEqual(result.type_scores["money_transfer"], 0.9)
        self.assertEqual(result.detected_types, ["money_transfer"])
        self.assertEqual(self.analyzer.model_version, "test-model-v1")

        self.predictor.predict.assert_called_once()
        sent_inputs = self.predictor.predict.call_args.args[0]
        self.assertEqual(len(sent_inputs), 1)
        self.assertEqual(
            sent_inputs[0].current_text,
            self.model_input.current_text,
        )
        self.assertEqual(
            sent_inputs[0].history_texts,
            list(self.model_input.history_texts),
        )

    def test_rejects_wrong_result_count(self):
        for outputs in ([], [self.output, self.output]):
            with self.subTest(count=len(outputs)):
                self.predictor.predict.return_value = outputs
                with self.assertRaises(ValueError):
                    self.analyzer.analyze(self.model_input)

    def test_rejects_invalid_probability(self):
        self.output.type_probabilities["money_transfer"] = 90.0

        with self.assertRaises(ValidationError):
            self.analyzer.analyze(self.model_input)

    def test_propagates_inference_failure(self):
        self.predictor.predict.side_effect = RuntimeError("inference failed")

        with self.assertRaisesRegex(RuntimeError, "inference failed"):
            self.analyzer.analyze(self.model_input)

    def test_shared_predictor_runs_one_inference_at_a_time(self):
        first_entered = Event()
        second_started = Event()
        second_entered = Event()
        release_first = Event()

        def predict(inputs):
            if not first_entered.is_set():
                first_entered.set()
                if not release_first.wait(2):
                    raise TimeoutError("first inference was not released")
            else:
                second_entered.set()
            return [self.output]

        def second_request():
            second_started.set()
            return self.analyzer.analyze(self.model_input)

        self.predictor.predict.side_effect = predict
        with ThreadPoolExecutor(max_workers=2) as executor:
            first = executor.submit(self.analyzer.analyze, self.model_input)
            try:
                self.assertTrue(first_entered.wait(1))
                second = executor.submit(second_request)
                self.assertTrue(second_started.wait(1))
                self.assertFalse(second_entered.wait(0.1))
            finally:
                release_first.set()
            self.assertEqual(0.82, first.result(timeout=2).is_phishing_score)
            self.assertEqual(0.82, second.result(timeout=2).is_phishing_score)
        self.assertTrue(second_entered.is_set())


if __name__ == "__main__":
    unittest.main()
