"""Input validation and normalization for utterance analysis."""

from __future__ import annotations


class InvalidTextError(ValueError):
    """Raised when an utterance cannot be analyzed as text."""


class TextTooLongError(ValueError):
    """Raised only when a caller supplies a maximum input length."""


def preprocess_text(text: object, *, max_length: int | None = None) -> str:
    """Validate and normalize one utterance.

    The project has no approved maximum input length.  ``max_length`` therefore
    defaults to ``None`` and is intentionally a caller-provided integration
    setting, rather than a module policy.  A future API or model adapter may
    pass its approved limit here.
    """

    if not isinstance(text, str):
        raise InvalidTextError("text must be a str")

    normalized_text = text.strip()
    if not normalized_text:
        raise InvalidTextError("text must not be empty or whitespace only")

    if max_length is not None:
        if not isinstance(max_length, int) or isinstance(max_length, bool) or max_length <= 0:
            raise ValueError("max_length must be a positive integer or None")
        if len(normalized_text) > max_length:
            raise TextTooLongError("text exceeds the caller-provided max_length")

    return normalized_text
