"""Reusable payloads and stand-ins for API tests; no external model calls."""

import json
from copy import deepcopy
from dataclasses import replace

from backend.services.ai_service import RiskModelScores
from backend.services.risk_service import ALLOWED_RISK_TYPES
from models.warning_manager.contracts import (
    ConversationWarningState, WarningEvent, WarningUpdate,
)


def payload(sequence=1, score=0.55, conversation_id="api-test"):
    return {
        "conversation_id": conversation_id,
        "utterance_id": sequence,
        "revision": 1,
        "sequence": sequence,
        "tuned_text": "계산 확인용 문장입니다.",
        "analysis_status": "ok" if score is not None else "error",
        "is_phishing_score": score,
        "type_scores": (
            {name: 0.2 for name in ALLOWED_RISK_TYPES}
            if score is not None else None
        ),
        "detected_types": [] if score is not None else None,
        "model_version": "sample-v1",
    }


def utterance(number=1, conversation_id="pipeline-test"):
    return {
        "schema_version": "1.0",
        "conversation_id": conversation_id,
        "utterance_id": number,
        "masked_text": f"문장 {number}",
        "has_masked_data": False,
        "masked_types": [],
    }


class StubCorrectionClient:
    def __init__(self):
        self.calls = 0
        self.fail = False

    def complete(self, *, system_prompt, user_prompt):
        self.calls += 1
        if self.fail:
            raise RuntimeError("private provider detail")
        text = json.loads(user_prompt.splitlines()[-1])["masked_text"]
        return json.dumps({"tuned_text": text + ".", "unclear_segments": []})


class StubRiskAnalyzer:
    model_version = "test-risk-v1"

    def __init__(self):
        self.inputs = []
        self.fail = False
        self.invalid_result = None

    def analyze(self, model_input):
        self.inputs.append(model_input)
        if self.fail:
            raise TimeoutError("private inference detail")
        if self.invalid_result is not None:
            return self.invalid_result
        return RiskModelScores(
            is_phishing_score=0.55,
            type_scores={name: 0.0 for name in ALLOWED_RISK_TYPES},
            detected_types=[],
        )


def evidence_for(state):
    if state is None or not state.individual_evidence:
        return {"recent": None, "highest": None, "cumulative_events": []}

    def item(utterance):
        return {
            "utterance_id": utterance.utterance_id,
            "text": utterance.tuned_text,
            "risk_score": 100 * utterance.is_phishing_score,
            "risk_types": list(utterance.detected_types),
        }

    return {
        "recent": item(state.individual_evidence[-1]),
        "highest": item(max(state.individual_evidence, key=lambda row: row.is_phishing_score)),
        "cumulative_events": [],
    }


class StubWarningManager:
    """성공 입력에 고정된 경고 시나리오를 반환하는 연동 테스트용 구현체."""

    def __init__(self):
        self.calls = []
        self.fail = False
        self.transform = lambda update: update

    def update_warning(self, model, calculation, previous, config, **flags):
        self.calls.append(deepcopy((model, calculation, previous, config, flags)))
        if self.fail:
            if previous is not None and previous.individual_evidence:
                previous.individual_evidence[0].type_scores["money_transfer"] = 1.0
            raise RuntimeError("private warning failure")
        if model.analysis_status == "error":
            state = previous
            status = previous.status if previous is not None else "none"
            reason = "single_utterance" if previous is not None else None
            notify = None
        else:
            event_id = "event-" + model.conversation_id
            if previous is None:
                events = (WarningEvent(
                    event_id=event_id, initial_calculation=calculation,
                    reason="single_utterance", peak_score=calculation.cumulative_score,
                    last_sequence=model.sequence, utterances=(model,),
                ),)
                evidence = (model,)
            else:
                events = (*previous.events[:-1], replace(
                    previous.events[-1], last_sequence=model.sequence,
                    peak_score=max(previous.events[-1].peak_score, calculation.cumulative_score),
                    utterances=(*previous.events[-1].utterances, model),
                ))
                evidence = (*previous.individual_evidence, model)
            status = "active"
            reason = "single_utterance"
            state = ConversationWarningState(
                conversation_id=model.conversation_id, config=config,
                status=status, cumulative_score=calculation.cumulative_score,
                individual_evidence=evidence, events=events,
            )
            # 같은 ID가 재요청되어도 서버 대기 목록은 한 번만 기록해야 한다.
            notify = event_id
        result = {
            "warning": {"status": status, "reason": reason, "message": "테스트 안내"},
            "evidence": evidence_for(state),
        }
        return self.transform(WarningUpdate(result=result, state=state, notify_event_id=notify))
