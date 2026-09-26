"""근거·경고 이력 인터페이스. 구현체 예: DefaultEvidenceManager."""

from collections.abc import Iterable
from dataclasses import replace
from typing import Protocol
from uuid import NAMESPACE_URL, uuid5

from .contracts import (
    CalculationResult,
    ConversationWarningState,
    CumulativeEventPayload,
    EvidenceItem,
    EvidencePayload,
    ModelRiskResult,
    WarningConfig,
    WarningDecision,
    WarningEvent,
)


class EvidenceManager(Protocol):
    def update(
        self,
        model_result: ModelRiskResult,
        calculation_result: CalculationResult,
        previous_state: ConversationWarningState | None,
        decision: WarningDecision,
        config: WarningConfig,
    ) -> ConversationWarningState:
        """성공한 점수·판단 → 개별 근거, 누적 근거, 이벤트를 갱신한 새 상태.
        첫 진입/재진입은 이벤트 생성, 활성 지속은 갱신, 기준 미만은 종료한다.
        최초 계산과 최고 누적값을 보존하고, 이전 상태를 직접 변경하지 않는다.
        """
        ...

    def build_payload(self, state: ConversationWarningState | None) -> EvidencePayload:
        """저장 근거 → 외부 evidence. 점수는 0~100.
        recent는 발생 순서 최대, highest는 개별 점수 최대(동점은 먼저 발생).
        cumulative_events는 first_cumulative의 최초 기여 발화와 점수로 구성한다.
        근거 없음은 recent/highest=None, cumulative_events=[].
        """
        ...

def _merge_evidence(
    existing: tuple[ModelRiskResult, ...],
    incoming: Iterable[ModelRiskResult],
) -> tuple[ModelRiskResult, ...]:
    """같은 발화 ID와 정정 버전은 한 번만 보존한다."""
    by_key = {
        (utterance.utterance_id, utterance.revision): utterance
        for utterance in existing
    }

    for utterance in incoming:
        key = (utterance.utterance_id, utterance.revision)
        by_key.setdefault(key, utterance)

    return tuple(
        sorted(by_key.values(), key=lambda utterance: utterance.sequence)
    )


def _contributors(
    calculation_result: CalculationResult,
) -> tuple[ModelRiskResult, ...]:
    """현재 계산 창에서 유효 위험값이 양수인 발화를 고른다."""
    return tuple(
        item.utterance
        for item in calculation_result.window_utterances
        if item.effective_risk > 0
    )


def _risk_score(utterance: ModelRiskResult) -> float:
    """보존된 근거의 개별 발화 점수를 읽는다."""
    score = utterance.is_phishing_score
    if utterance.analysis_status != "ok" or score is None:
        raise ValueError("저장된 근거에는 성공한 분석 점수가 필요합니다.")
    return score


def _to_evidence_item(utterance: ModelRiskResult) -> EvidenceItem:
    """내부 발화 객체를 앱에 전달할 근거 형식으로 바꾼다."""
    if utterance.detected_types is None:
        raise ValueError("저장된 근거에는 감지 유형 결과가 필요합니다.")

    return {
        "utterance_id": utterance.utterance_id,
        "text": utterance.tuned_text,
        "risk_score": _risk_score(utterance) * 100,
        "risk_types": list(utterance.detected_types),
    }


class DefaultEvidenceManager:
    """개별 근거와 경고 이벤트를 관리하고 외부 근거를 구성한다."""

    def update(
        self,
        model_result: ModelRiskResult,
        calculation_result: CalculationResult,
        previous_state: ConversationWarningState | None,
        decision: WarningDecision,
        config: WarningConfig,
    ) -> ConversationWarningState:
        score = model_result.is_phishing_score
        if (
            model_result.analysis_status != "ok"
            or score is None
            or model_result.type_scores is None
            or model_result.detected_types is None
        ):
            raise ValueError("근거 갱신에는 성공한 분석 결과가 필요합니다.")

        individual = (
            previous_state.individual_evidence
            if previous_state is not None
            else ()
        )
        events = previous_state.events if previous_state is not None else ()

        if score * 100 >= config.evidence_threshold:
            individual = _merge_evidence(individual, (model_result,))

        if decision.status == "active":
            if decision.reason is None:
                raise ValueError("활성 경고에는 사유가 필요합니다.")

            cumulative_now = (
                calculation_result.accumulated_score
                >= config.warning_threshold
            )
            incoming = (
                _contributors(calculation_result)
                if cumulative_now
                else ()
            )

            if previous_state is not None and previous_state.status == "active":
                if not events or events[-1].closed_sequence is not None:
                    raise ValueError("갱신할 활성 경고 이벤트가 없습니다.")

                prior = events[-1]
                first_cumulative = prior.first_cumulative
                if first_cumulative is None and cumulative_now:
                    first_cumulative = calculation_result

                updated = replace(
                    prior,
                    reason=decision.reason,
                    peak_score=max(
                        prior.peak_score,
                        calculation_result.cumulative_score,
                    ),
                    last_sequence=model_result.sequence,
                    first_cumulative=first_cumulative,
                    utterances=_merge_evidence(
                        prior.utterances,
                        incoming,
                    ),
                )
                events = events[:-1] + (updated,)
            else:
                event_id = str(
                    uuid5(
                        NAMESPACE_URL,
                        (
                            f"warning:{model_result.conversation_id}:"
                            f"{model_result.sequence}:"
                            f"{model_result.utterance_id}:"
                            f"{model_result.revision}"
                        ),
                    )
                )

                new_event = WarningEvent(
                    event_id=event_id,
                    initial_calculation=calculation_result,
                    reason=decision.reason,
                    peak_score=calculation_result.cumulative_score,
                    last_sequence=model_result.sequence,
                    first_cumulative=(
                        calculation_result if cumulative_now else None
                    ),
                    utterances=_merge_evidence((), incoming),
                )
                events = events + (new_event,)

        elif previous_state is not None and previous_state.status == "active":
            if not events or events[-1].closed_sequence is not None:
                raise ValueError("종료할 활성 경고 이벤트가 없습니다.")

            closed = replace(
                events[-1],
                closed_sequence=model_result.sequence,
            )
            events = events[:-1] + (closed,)

        return ConversationWarningState(
            conversation_id=model_result.conversation_id,
            config=config,
            status=decision.status,
            cumulative_score=calculation_result.cumulative_score,
            individual_evidence=individual,
            events=events,
        )

    def build_payload(
        self,
        state: ConversationWarningState | None,
    ) -> EvidencePayload:
        if state is None:
            return {
                "recent": None,
                "highest": None,
                "cumulative_events": [],
            }

        all_evidence = _merge_evidence(
            state.individual_evidence,
            (
                utterance
                for event in state.events
                for utterance in event.utterances
            ),
        )

        recent = max(
            all_evidence,
            key=lambda utterance: utterance.sequence,
            default=None,
        )
        highest = max(
            all_evidence,
            key=lambda utterance: (
                _risk_score(utterance),
                -utterance.sequence,
            ),
            default=None,
        )

        cumulative_events: list[CumulativeEventPayload] = []
        for event in state.events:
            first = event.first_cumulative
            if first is None:
                continue

            cumulative_events.append(
                {
                    "trigger_utterance_id": first.utterance_id,
                    "risk_score": first.cumulative_score,
                    "utterances": [
                        _to_evidence_item(utterance)
                        for utterance in _contributors(first)
                    ],
                }
            )

        return {
            "recent": (
                _to_evidence_item(recent) if recent is not None else None
            ),
            "highest": (
                _to_evidence_item(highest) if highest is not None else None
            ),
            "cumulative_events": cumulative_events,
        }
