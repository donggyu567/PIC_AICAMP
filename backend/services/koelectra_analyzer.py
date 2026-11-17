"""서버의 위험 분석 인터페이스를 KoELECTRA 추론 모듈과 연결한다."""

from collections.abc import Sequence
from threading import Lock
from typing import Protocol

from backend.services.ai_service import RiskModelInput, RiskModelScores
from risk_speech_ai.inference import (
    InferenceInput,
    InferenceOutput,
)


class RiskPredictor(Protocol):
    """개발용·학습 모델용 추론 객체가 제공해야 하는 공통 계약."""

    def predict(
        self,
        inputs: Sequence[InferenceInput],
    ) -> list[InferenceOutput]:
        ...


class KoElectraRiskAnalyzer:
    def __init__(
        self,
        predictor: RiskPredictor,
        *,
        model_version: str,
    ) -> None:
        if (
            not isinstance(model_version, str)
            or not model_version.strip()
            or len(model_version) > 120
        ):
            raise ValueError("model_version은 1~120자의 문자열이어야 합니다.")

        self._predictor = predictor
        self._prediction_lock = Lock()
        self.model_version = model_version

    def analyze(self, model_input: RiskModelInput) -> RiskModelScores:
        #서버에서 준비한 현재 문장과 이전 문맥을 AI 입력으로 변환
        inference_input = InferenceInput(
            current_text = model_input.current_text,
            history_texts = list(model_input.history_texts)
        )

        #AI는 여러 발화 한 번에 처리 가능, 목록으로 전달
        # 여러 통화가 공유하는 모델·토크나이저의 추론 구간만 보호한다.
        with self._prediction_lock:
            results = self._predictor.predict([inference_input])

        #현재 서버 요청은 발화 하나 -> 결과도 정확히 하나
        if len(results) != 1:
            raise ValueError("AI는 현재 발화에 대해 하나의 결과를 반환해야 합니다.")

        result = results[0]

        if not isinstance(result, InferenceOutput):
            raise TypeError("AI 결과는 InferenceOutput이어야합니다.")

        return RiskModelScores.model_validate(
            {
                "is_phishing_score" : result.risk_probability,
                "type_scores" : result.type_probabilities,
                "detected_types" : result.detected_types
            }
        )
