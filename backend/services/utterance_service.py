"""통합 분석에서 사용하는 발화 검증과 보정 엔진 생성."""

from functools import lru_cache
from models.llm_correction import (
    CorrectionEngine,
    MaskedTranscript,
    OpenAIResponsesClient,
)


def validate_utterance(payload: dict[str, object]) -> MaskedTranscript:
    return MaskedTranscript.from_dict(payload)


@lru_cache(maxsize=1)
def get_correction_engine() -> CorrectionEngine:
    return CorrectionEngine(OpenAIResponsesClient())

