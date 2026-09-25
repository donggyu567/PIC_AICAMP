from typing import Literal

from models.warning_manager.contracts import (
    CalculationResult,
    ModelRiskResult,
    RiskType,
    TypeSignals,
)


def build_model_result(
    *,
    conversation_id: str,
    utterance_id: int,
    revision: int,
    sequence: int,
    tuned_text: str,
    analysis_status: Literal["ok", "error"],
    is_phishing_score: float | None,
    type_scores: TypeSignals | None,
    detected_types: tuple[RiskType, ...] | None,
    model_version: str,
) -> ModelRiskResult:
    """현재 발화 정보와 AI 분석 결과를 공통 입력 객체로 구성한다."""
    raise NotImplementedError


def calculate_risk(
    utterances: list[ModelRiskResult],
    *,
    window_size: int,
    rho: float,
    b: float,
    policy_version: str,
) -> CalculationResult:
    """현재 발화를 포함한 최근 분석 결과로 누적 위험도를 계산한다."""
    raise NotImplementedError