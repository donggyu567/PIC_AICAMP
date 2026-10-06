from typing import Annotated, Literal, Self
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from backend.services.risk_service import build_model_result
from models.warning_manager.contracts import (
    EvidencePayload, ModelRiskResult, RiskType, WarningPayload,
)

class UtteranceRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    schema_version: Literal["1.0"]
    conversation_id: str = Field(min_length=1, max_length=120)
    utterance_id: int = Field(ge=1)
    masked_text: str = Field(min_length=1, max_length=10_000)
    has_masked_data: bool
    masked_types: list[str]


class UtteranceAnalysisRetryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    conversation_id: str = Field(min_length=1, max_length=120)
    utterance_id: int = Field(ge=1)


class ConversationEndRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    conversation_id: str = Field(min_length=1, max_length=120, pattern=r"\S")


class ConversationEndResponse(BaseModel):
    conversation_id: str
    conversation_status: Literal["ended"] = "ended"
    ended_at: AwareDatetime


ModelScore = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
DisplayScore = Annotated[float, Field(ge=0, le=100, allow_inf_nan=False)]


class ModelResultRequest(BaseModel):
    """개발용 AI 결과 입력. 점수 단위는 0~1, 신규·실패 재시도 모두 revision=1."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        json_schema_extra={
            "example": {
                "conversation_id": "api-test-001",
                "utterance_id": 1,
                "revision": 1,
                "sequence": 1,
                "tuned_text": "계산 확인용 문장입니다.",
                "analysis_status": "ok",
                "is_phishing_score": 0.55,
                "type_scores": {
                    "institution_impersonation": 0.0,
                    "money_transfer": 0.0,
                    "personal_information": 0.0,
                    "app_installation": 0.0,
                    "secrecy": 0.0,
                    "threat_pressure": 0.0,
                    "loan_fraud": 0.0,
                    "information_probing": 0.0,
                },
                "detected_types": [],
                "model_version": "sample-v1",
            }
        },
    )

    conversation_id: str = Field(min_length=1, max_length=120)
    utterance_id: int = Field(ge=1)
    revision: int = Field(ge=1, le=1)
    sequence: int = Field(ge=1)
    tuned_text: str = Field(min_length=1, max_length=10_000)
    analysis_status: Literal["ok", "error"]
    is_phishing_score: ModelScore | None
    type_scores: dict[RiskType, ModelScore] | None
    detected_types: list[RiskType] | None
    model_version: str = Field(min_length=1, max_length=120)

    def to_model_result(self) -> ModelRiskResult:
        data = self.model_dump()
        if self.detected_types is not None:
            data["detected_types"] = tuple(self.detected_types)
        return build_model_result(**data)

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        # 성공 시 8개 점수 필수, 실패 시 세 점수·유형 필드 모두 null.
        self.to_model_result()
        return self


class CalculationDetails(BaseModel):
    window_max_score: DisplayScore
    accumulated_score: DisplayScore
    window_utterance_ids: list[int]
    window_size: int
    rho: float
    b: float
    policy_version: str


class CalculationPreviewResponse(BaseModel):
    """표시 점수는 0~100. 경고 구현체 미연결 시 warning/evidence는 None."""

    conversation_id: str
    utterance_id: int
    revision: int
    sequence: int
    analysis_status: Literal["ok", "error"]
    current_text: str
    current_risk_score: DisplayScore | None
    cumulative_risk_score: DisplayScore | None
    type_scores: dict[RiskType, DisplayScore] | None
    detected_types: list[RiskType] | None
    calculation: CalculationDetails | None
    warning: WarningPayload | None = None
    evidence: EvidencePayload | None = None

    @model_validator(mode="after")
    def validate_warning_pair(self) -> Self:
        if (self.warning is None) != (self.evidence is None):
            raise ValueError("warning과 evidence는 함께 제공하거나 함께 null이어야 합니다.")
        return self
