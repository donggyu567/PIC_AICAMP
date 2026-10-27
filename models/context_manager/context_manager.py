"""Recent conversation context management with no risk-decision logic."""

from __future__ import annotations

from .schemas import ConversationContext, Utterance


class ConversationContextManager:
    """Keep the latest utterance and configurable preceding history."""

    def __init__(self, history_size: int = 5) -> None:
        if (
            not isinstance(history_size, int)
            or isinstance(history_size, bool)
            or history_size < 0
        ):
            raise ValueError("history_size must be a non-negative integer")
        self.history_size = history_size
        self._utterances: dict[str, dict[int, Utterance]] = {}
        self._seen_ids: set[tuple[str, int]] = set()
        self._current_conversation_id: str | None = None

    def add(self, utterance: Utterance) -> ConversationContext:
        """Add an utterance and return the current sorted context.

        Duplicate IDs within a conversation are rejected even when an older
        utterance has fallen out of the retained context.
        """

        if not isinstance(utterance, Utterance):
            raise TypeError("utterance must be an Utterance")
        utterance_key = (utterance.conversation_id, utterance.utterance_id)
        if utterance_key in self._seen_ids:
            raise ValueError(
                "duplicate conversation_id and utterance_id: "
                f"{utterance.conversation_id}, {utterance.utterance_id}"
            )

        self._seen_ids.add(utterance_key)
        conversation = self._utterances.setdefault(utterance.conversation_id, {})
        conversation[utterance.utterance_id] = utterance
        self._current_conversation_id = utterance.conversation_id
        self._discard_older_utterances(utterance.conversation_id)
        return self.get_context(utterance.conversation_id)

    def get_context(self, conversation_id: str | None = None) -> ConversationContext:
        """Return one conversation's latest ID and preceding IDs as context."""

        selected_conversation_id = (
            conversation_id
            if conversation_id is not None
            else self._current_conversation_id
        )
        if (
            selected_conversation_id is None
            or selected_conversation_id not in self._utterances
        ):
            raise ValueError("cannot create conversation context without utterances")

        utterances = self._utterances[selected_conversation_id]
        ordered = [utterances[key] for key in sorted(utterances)]
        return ConversationContext(current=ordered[-1], history=ordered[:-1])

    def _discard_older_utterances(self, conversation_id: str) -> None:
        retained_size = self.history_size + 1
        utterances = self._utterances[conversation_id]
        ordered_ids = sorted(utterances)
        for utterance_id in ordered_ids[:-retained_size]:
            del utterances[utterance_id]
