"""파일 저장소와 신규 요청이 공유하는 발화 순서 검증."""

from backend.schemas import ModelResultRequest


class AnalysisConflictError(ValueError):
    """저장된 분석 결과와 신규 발화의 ID 또는 순서가 충돌한 경우."""


def validate_new_result(
    result: ModelResultRequest,
    *,
    seen_ids: set[int],
    expected_sequence: int,
) -> None:
    """이미 검증된 결과의 신규 버전·중복·순서를 확인한다."""
    if result.revision != 1:
        raise ValueError("신규 발화는 revision이 1이어야 합니다.")
    if result.utterance_id in seen_ids:
        raise AnalysisConflictError("이미 저장된 발화입니다.")
    if result.sequence != expected_sequence:
        raise AnalysisConflictError(f"다음 sequence는 {expected_sequence}여야 합니다.")
