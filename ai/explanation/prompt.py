"""Safe prompt text and deterministic fallback for recommendation explanations."""

from __future__ import annotations

from .schemas import ExplanationInput, ExplanationOutput


DECISION_NOTE = (
    "AI 추천은 우선 검토 제안이며, 실제 설치 가능 여부는 현장 여건과 행정 검토를 통해 최종 결정해야 합니다."
)

FACTOR_LABELS = {
    "HIGH_ELDERLY_RATIO": "고령인구 비율이 높은 지역",
    "HIGH_FARMLAND_RATIO": "농경지 비중이 높은 지역",
    "LOW_SHELTER_ACCESSIBILITY": "기존 쉼터 접근성이 낮은 지역",
    "HIGH_HEAT": "열 노출 위험이 높은 지역",
}

SYSTEM_PROMPT = """당신은 지방자치단체 담당자를 위한 AI 추천 설명 보조자입니다.
제공된 JSON의 사실과 숫자만 사용해 후보별 추천 설명을 한국어 2~4문장으로 작성하세요.
후보 선택, 추천 순위, 점수, 위험등급, blind_spot을 변경하거나 재계산하지 마세요.
입력에 없는 좌표·거리·시설 정보·설치 가능성·효과 수치를 만들지 마세요.
설치를 확정적으로 권고하지 말고 반드시 '우선 검토 제안'으로 표현하세요.
'최적', '반드시 설치', 'AI가 설치를 결정' 같은 표현을 사용하지 마세요.
출력은 candidate_id, summary, key_reasons(2~3개), expected_effect, decision_note 구조를 따르세요."""


def format_percentage(value: float | None) -> str | None:
    """Format a 0..1 ratio for display without altering the underlying value."""
    if value is None:
        return None
    return f"{value * 100:.1f}%"


def build_fallback_explanation(payload: ExplanationInput) -> ExplanationOutput:
    """Create a deterministic, fact-only explanation when an LLM is unavailable."""
    reasons = _key_reasons(payload)
    summary = (
        f"{payload.candidate_name}은(는) AI 분석에서 {payload.recommendation_rank}순위 우선 검토 후보로 선정되었습니다."
    )
    effect = _expected_effect(payload)
    return ExplanationOutput(
        candidate_id=payload.candidate_id,
        summary=summary,
        key_reasons=tuple(reasons[:3]),
        expected_effect=effect,
        decision_note=DECISION_NOTE,
    )


def _key_reasons(payload: ExplanationInput) -> list[str]:
    reasons: list[str] = []
    for grid in payload.covered_grids:
        for factor in grid.main_factors:
            label = FACTOR_LABELS.get(factor)
            if label and label not in reasons:
                reasons.append(label)
    if payload.newly_covered_grid_count:
        reasons.append(f"현재 보호받지 못하는 취약 Grid {payload.newly_covered_grid_count}개를 새로 보호할 수 있는 후보")
    if not reasons:
        reasons.append("제공된 AI 분석 결과를 기준으로 한 우선 검토 후보")
    return reasons


def _expected_effect(payload: ExplanationInput) -> str:
    parts = [
        f"이 후보를 활용하면 취약 Grid {payload.newly_covered_grid_count}개와 고령인구 {payload.newly_covered_elderly_population}명을 추가로 보호할 수 있는 것으로 분석되었습니다."
    ]
    before = format_percentage(_number_or_none(payload.before.get("vulnerable_population_coverage_rate")))
    after = format_percentage(_number_or_none(payload.after.get("vulnerable_population_coverage_rate")))
    delta = format_percentage(_number_or_none(payload.overall_improvement.get("vulnerable_population_coverage_rate_delta")))
    if before is not None and after is not None and delta is not None:
        parts.append(f"전체 취약 고령인구 보호율은 {before}에서 {after}로 {delta}p 증가하는 결과와 연결됩니다.")
    return " ".join(parts)


def _number_or_none(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)
