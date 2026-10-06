from functools import lru_cache
from threading import Lock

from models.context_manager import(
    ConversationContext,
    ConversationContextManager,
    merge_utterance
)
from models.llm_correction import (
    CorrectionEngine,
    MaskedTranscript,
    OpenAIResponsesClient
)


class UtteranceOrderError(ValueError):
    pass

context_manager = ConversationContextManager(history_size=5)
next_utterance_ids: dict[str,int] = {}
processing_lock = Lock()


def validate_utterance(payload: dict[str, object])-> MaskedTranscript:
    return MaskedTranscript.from_dict(payload)

@lru_cache(maxsize=1)
def get_correction_engine() -> CorrectionEngine:
    client = OpenAIResponsesClient()
    return CorrectionEngine(client)

def process_utterance(payload: dict[str,object]) -> ConversationContext:
    transcript = validate_utterance(payload)

    with processing_lock:
        conversation_id = transcript.conversation_id
        excepted_id = next_utterance_ids.get(conversation_id, 1)

        if transcript.utterance_id != excepted_id:
            raise UtteranceOrderError(
                f"다음 utterance__id는 {excepted_id}여야 합니다."
            )

        engine = get_correction_engine()
        correction = engine.correct(transcript)

        utterance = merge_utterance(
            transcript.to_dict(),
            correction.to_dict()
        )

        context = context_manager.add(utterance)
        next_utterance_ids[conversation_id] = excepted_id+1

        return context

