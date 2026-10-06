"""위험 탐지 AI 연결 계약. 모델 로딩·추론은 별도 어댑터가 제공한다."""

from dataclasses import dataclass
from typing import Protocol, Self

from pydantic import BaseModel, ConfigDict, model_validator

from backend.schemas import ModelScore
from backend.services.risk_service import ALLOWED_RISK_TYPES
from models.warning_manager.contracts import RiskType


@dataclass(frozen=True)
class RiskModelInput:
    """현재 문장과 오래된 순서의 이전 최대 5개 보정 문장."""

    current_text: str
    history_texts: tuple[str, ...]


class RiskModelScores(BaseModel):
    """AI가 반환할 현재 발화의 점수. 모두 0~1 단위다."""

    model_config = ConfigDict(extra="forbid", strict=True)

    is_phishing_score: ModelScore
    type_scores: dict[RiskType, ModelScore]
    detected_types: list[RiskType]

    @model_validator(mode="after")
    def validate_types(self) -> Self:
        if set(self.type_scores) != ALLOWED_RISK_TYPES:
            raise ValueError("AI 결과에는 8개 유형 점수가 모두 필요합니다.")
        if len(self.detected_types) != len(set(self.detected_types)):
            raise ValueError("AI 감지 유형은 중복될 수 없습니다.")
        return self


class RiskAnalyzer(Protocol):
    model_version: str

    def analyze(self, model_input: RiskModelInput) -> RiskModelScores:
        """추론 성공 시 점수를 반환하고 실패 시 예외를 발생시킨다.

        tokenizer 길이 제한과 실제 모델 출력 변환은 구현체에서 처리한다.
        감지 유형은 모델 또는 합의된 임계값으로 구성해야 한다.
        """
        ...
