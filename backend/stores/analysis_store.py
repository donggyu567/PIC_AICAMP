from copy import deepcopy

from models.warning_manager.contracts import ModelRiskResult


class AnalysisConflictError(ValueError):
    """저장된 분석 결과와 신규 발화의 ID 또는 순서가 충돌한 경우."""


class AnalysisStore:
    """통화별 발화 분석 결과를 메모리에 저장한다."""

    def __init__(self) -> None:
        self._results: dict[str, list[ModelRiskResult]] = {}

    def validate_new(self, result: ModelRiskResult) -> None:
        """저장 내용을 변경하지 않고 신규 발화의 추가 가능 여부를 확인한다."""
        if not isinstance(result, ModelRiskResult):
            raise ValueError("ModelRiskResult 객체가 필요합니다.")

        # 정정 결과는 이후 별도의 재처리 흐름으로 처리한다.
        if result.revision != 1:
            raise ValueError("신규 발화는 revision이 1이어야 합니다.")

        history = self._results.get(result.conversation_id, [])

        if any(
            item.utterance_id == result.utterance_id
            for item in history
        ):
            raise AnalysisConflictError("이미 저장된 발화입니다.")

        expected_sequence = len(history) + 1

        if result.sequence != expected_sequence:
            raise AnalysisConflictError(
                f"다음 sequence는 {expected_sequence}여야 합니다."
            )

    def add(self, result: ModelRiskResult) -> None:
        """검증된 신규 발화 결과를 발생 순서대로 추가한다."""
        self.validate_new(result)

        # 호출자가 원본 객체를 변경해도 저장된 값은 유지한다.
        saved_result = deepcopy(result)

        self._results.setdefault(
            result.conversation_id, []
        ).append(saved_result)

    def get_history(
        self,
        conversation_id: str,
    ) -> list[ModelRiskResult]:
        """해당 통화의 분석 결과를 발생 순서대로 반환한다."""
        history = self._results.get(conversation_id, [])

        # 반환된 목록을 수정해도 저장소에는 영향을 주지 않는다.
        return deepcopy(history)
