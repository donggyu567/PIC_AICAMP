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
        self._utterances: dict[int, Utterance] = {}
        self._seen_ids: set[int] = set()

    def add(self, utterance: Utterance) -> ConversationContext:
        """Add an utterance and return the current sorted context.

        Duplicate IDs are rejected even when an older utterance has fallen out
        of the retained context, preventing silent replacement.
        """

        if not isinstance(utterance, Utterance):
            raise TypeError("utterance must be an Utterance")
        if utterance.utterance_id in self._seen_ids:
            raise ValueError(f"duplicate utterance_id: {utterance.utterance_id}")

        self._seen_ids.add(utterance.utterance_id)
        self._utterances[utterance.utterance_id] = utterance
        self._discard_older_utterances()
        return self.get_context()

    def get_context(self) -> ConversationContext:
        """Return the latest ID as current and preceding IDs as history."""

        if not self._utterances:
            raise ValueError("cannot create conversation context without utterances")

        ordered = [self._utterances[key] for key in sorted(self._utterances)]
        return ConversationContext(current=ordered[-1], history=ordered[:-1])

    def _discard_older_utterances(self) -> None:
        retained_size = self.history_size + 1
        ordered_ids = sorted(self._utterances)
        for utterance_id in ordered_ids[:-retained_size]:
            del self._utterances[utterance_id]
