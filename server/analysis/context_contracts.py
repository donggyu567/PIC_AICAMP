"""문맥 판단 입력과 외부 응답 경계 검증. 출력 타입은 저장 스키마와 공유한다."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from backend.schemas import ContextRiskJudgment
from models.llm_correction import validate_masking_token_preservation


UtteranceId = Annotated[int, Field(ge=1)]


class ContextUtterance(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    utterance_id: UtteranceId
    text: str = Field(min_length=1, max_length=10_000, repr=False)


class ContextRiskInput(BaseModel):
    """서버가 같은 통화의 기록을 순서대로 구성한다. 현재 발화가 마지막이다."""

    model_config = ConfigDict(extra="forbid", strict=True)

    conversation_id: str = Field(min_length=1, max_length=120)
    current_utterance_id: UtteranceId
    utterances: list[ContextUtterance] = Field(min_length=1, repr=False)


class PreparedUtterance(BaseModel):
    """OpenAI 단일 호출 출력. ID와 실행 상태는 서버가 붙인다."""

    model_config = ConfigDict(extra="forbid", strict=True)

    corrected_text: str = Field(min_length=1, max_length=10_000, repr=False)
    context_judgment: ContextRiskJudgment


def parse_prepared_utterance(payload: str, context: ContextRiskInput) -> PreparedUtterance:
    """외부 응답 경계에서 문장·마스킹 토큰·근거 참조를 확인한다."""
    prepared = PreparedUtterance.model_validate_json(payload)
    validate_masking_token_preservation(context.utterances[-1].text, prepared.corrected_text)
    judgment = prepared.context_judgment
    available_ids = {utterance.utterance_id for utterance in context.utterances}
    if not set(judgment.evidence_utterance_ids) <= available_ids:
        raise ValueError("문맥 입력에 없는 발화를 근거로 사용할 수 없습니다.")
    if judgment.assessment == "suspicious" and not judgment.evidence_utterance_ids:
        raise ValueError("문맥 위험 판단에는 근거 발화가 필요합니다.")
    return prepared
