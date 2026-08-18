"""JSON-serializable data structures for task 3 conversation input."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Utterance:
    """One masked utterance combined with its task 2 correction result."""

    utterance_id: int
    masked_text: str
    has_masked_data: bool
    masked_types: list[str]
    tuned_text: str
    is_tuned: bool
    has_unclear: bool
    unclear_segments: list[str]

    def to_dict(self) -> dict[str, object]:
        """Return the exact task 3 utterance JSON shape."""

        return {
            "utterance_id": self.utterance_id,
            "masked_text": self.masked_text,
            "has_masked_data": self.has_masked_data,
            "masked_types": list(self.masked_types),
            "tuned_text": self.tuned_text,
            "is_tuned": self.is_tuned,
            "has_unclear": self.has_unclear,
            "unclear_segments": list(self.unclear_segments),
        }


@dataclass(frozen=True)
class ConversationContext:
    """The latest utterance and its immediately preceding conversation."""

    current: Utterance
    history: list[Utterance]

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable context for a later risk-sensitivity AI."""

        return {
            "current": self.current.to_dict(),
            "history": [utterance.to_dict() for utterance in self.history],
        }
