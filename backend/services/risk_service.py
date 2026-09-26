from math import isfinite, prod
from typing import Literal, get_args

from models.warning_manager.contracts import (
    CalculationResult,
    ModelRiskResult,
    RiskType,
    TypeSignals,
    WindowUtterance,
)


ALLOWED_RISK_TYPES = frozenset(get_args(RiskType))


def validate_score(value: object) -> None:
    """점수가 유한한 0~1 숫자인지 검사한다."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("점수는 숫자여야 합니다.")

    if not 0 <= value <= 1 or not isfinite(value):
        raise ValueError("점수는 유한한 0~1 값이어야 합니다.")


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
    """발화 정보와 AI 분석 결과를 검증하여 공통 객체로 만든다."""

    # 1. 문자열 검사
    for name, value in (
        ("conversation_id", conversation_id),
        ("tuned_text", tuned_text),
        ("model_version", model_version),
    ):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"{name}은 비어 있지 않은 문자열이어야 합니다."
            )

    # 2. 식별자·버전·발생 순서 검사
    for name, value in (
        ("utterance_id", utterance_id),
        ("revision", revision),
        ("sequence", sequence),
    ):
        if type(value) is not int or value < 1:
            raise ValueError(f"{name}은 1 이상의 정수여야 합니다.")

    # 3. 분석 상태에 따른 검사
    if analysis_status == "error":
        if (
            is_phishing_score is not None
            or type_scores is not None
            or detected_types is not None
        ):
            raise ValueError(
                "분석 실패 시 점수·유형 필드는 모두 None이어야 합니다."
            )

    elif analysis_status == "ok":
        validate_score(is_phishing_score)

        if not isinstance(type_scores, dict):
            raise ValueError("분석 성공 시 유형별 점수가 필요합니다.")

        if set(type_scores) != ALLOWED_RISK_TYPES:
            raise ValueError(
                "유형별 점수에는 정확히 8개 위험 유형이 필요합니다."
            )

        for score in type_scores.values():
            validate_score(score)

        if not isinstance(detected_types, tuple):
            raise ValueError("detected_types는 tuple이어야 합니다.")

        for risk_type in detected_types:
            if (
                not isinstance(risk_type, str)
                or risk_type not in ALLOWED_RISK_TYPES
            ):
                raise ValueError("허용되지 않은 위험 유형입니다.")

        if len(detected_types) != len(set(detected_types)):
            raise ValueError("감지 유형은 중복될 수 없습니다.")

    else:
        raise ValueError("analysis_status는 ok 또는 error여야 합니다.")

    # 4. 검증을 통과한 데이터로 객체 생성
    return ModelRiskResult(
        conversation_id=conversation_id,
        utterance_id=utterance_id,
        revision=revision,
        sequence=sequence,
        tuned_text=tuned_text,
        analysis_status=analysis_status,
        is_phishing_score=(
            float(is_phishing_score)
            if is_phishing_score is not None
            else None
        ),
        type_scores=type_scores.copy() if type_scores is not None else None,
        detected_types=detected_types,
        model_version=model_version,
    )


def calculate_risk(
    utterances: list[ModelRiskResult],
    *,
    window_size: int,
    rho: float,
    b: float,
    policy_version: str,
) -> CalculationResult:
    """최근 발화 점수로 누적 위험도와 발화별 기여 내역을 계산한다."""

    # 1. 계산 설정 검사
    if type(window_size) is not int or window_size < 1:
        raise ValueError("window_size는 1 이상의 정수여야 합니다.")

    validate_score(rho)
    validate_score(b)

    if rho == 0:
        raise ValueError("rho는 0보다 크고 1 이하여야 합니다.")

    if b == 1:
        raise ValueError("b는 0 이상 1 미만이어야 합니다.")

    if not isinstance(policy_version, str) or not policy_version.strip():
        raise ValueError("policy_version이 필요합니다.")

    if not isinstance(utterances, list) or not utterances:
        raise ValueError("계산할 발화 목록이 필요합니다.")

    # 2. 통화·순서·중복·분석 성공 여부 검사
    seen_ids: set[int] = set()
    previous_sequence: int | None = None
    conversation_id: str | None = None

    for utterance in utterances:
        if not isinstance(utterance, ModelRiskResult):
            raise ValueError("ModelRiskResult 객체가 필요합니다.")

        for value in (
            utterance.utterance_id,
            utterance.revision,
            utterance.sequence,
        ):
            if type(value) is not int or value < 1:
                raise ValueError("발화 ID·버전·순서는 양의 정수여야 합니다.")

        if conversation_id is None:
            conversation_id = utterance.conversation_id

        if utterance.conversation_id != conversation_id:
            raise ValueError("서로 다른 통화의 발화를 함께 계산할 수 없습니다.")

        if utterance.utterance_id in seen_ids:
            raise ValueError("중복 발화 또는 여러 정정 버전이 포함되어 있습니다.")

        if (
            previous_sequence is not None
            and utterance.sequence != previous_sequence + 1
        ):
            raise ValueError("발화 발생 순서는 누락 없이 연속이어야 합니다.")

        if utterance.analysis_status != "ok":
            raise ValueError("분석 실패 발화가 포함되어 계산할 수 없습니다.")

        validate_score(utterance.is_phishing_score)

        seen_ids.add(utterance.utterance_id)
        previous_sequence = utterance.sequence

    # 3. 현재 발화와 최근 계산 창 선택
    current = utterances[-1]
    window = utterances[-window_size:]

    expected_count = min(window_size, current.sequence)
    if len(window) != expected_count:
        raise ValueError("계산에 필요한 이전 발화가 부족합니다.")

    # 4. 발화별 기여 내역 계산
    window_utterances: list[WindowUtterance] = []
    scores: list[float] = []

    for utterance in window:
        score = float(utterance.is_phishing_score)
        age = current.sequence - utterance.sequence

        weight = rho ** age
        effective_risk = max(0.0, (score - b) / (1.0 - b))
        contribution = weight * effective_risk

        window_utterances.append(
            WindowUtterance(
                utterance=utterance,
                weight=weight,
                effective_risk=effective_risk,
                contribution=contribution,
            )
        )
        scores.append(score)

    # 5. 창 최대 점수와 누적 점수 계산
    window_max = max(scores)
    accumulated = 1.0 - prod(
        1.0 - item.contribution
        for item in window_utterances
    )

    # 6. 표시 점수 단위인 0~100으로 변환해 반환
    return CalculationResult(
        conversation_id=current.conversation_id,
        utterance_id=current.utterance_id,
        revision=current.revision,
        window_max_score=100.0 * window_max,
        accumulated_score=100.0 * accumulated,
        cumulative_score=100.0 * max(window_max, accumulated),
        window_utterances=tuple(window_utterances),
        policy_version=policy_version,
        window_size=window_size,
        rho=rho,
        b=b,
    )