"""학습 전 판단층을 사용하는 개발용 AI 연결. 점수는 연결 확인용이다."""

from collections.abc import Sequence
from uuid import uuid4

from backend.services.koelectra_analyzer import KoElectraRiskAnalyzer
from risk_speech_ai.inference import (
    InferenceInput,
    InferenceOutput,
    ThresholdConfig,
    infer_batch,
)
from risk_speech_ai.model import RiskSpeechClassifier
from risk_speech_ai.tokenization import load_koelectra_tokenizer


class DevelopmentPredictor:
    def __init__(self) -> None:
        self.tokenizer = load_koelectra_tokenizer()

        # 기본 KoELECTRA는 사전학습됐지만 판단층은 새로 초기화된 상태다.
        self.model = RiskSpeechClassifier()
        self.model.to("cpu")
        self.model.eval()
        self.thresholds = ThresholdConfig()

    def predict(
        self,
        inputs: Sequence[InferenceInput],
    ) -> list[InferenceOutput]:
        return infer_batch(
            self.model,
            inputs,
            tokenizer=self.tokenizer,
            thresholds=self.thresholds,
            device="cpu",
        )


def load_development_analyzer() -> KoElectraRiskAnalyzer:
    predictor = DevelopmentPredictor()

    # 새로 초기화한 개발용 모델을 저장 기록에서 구분한다.
    model_version = f"development-untrained-{uuid4().hex[:12]}"
    return KoElectraRiskAnalyzer(
        predictor,
        model_version=model_version,
    )
