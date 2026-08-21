"""Provider-independent interface used by the STT correction engine."""

from __future__ import annotations

from typing import Protocol


class LLMClient(Protocol):
    """Minimum capability required from an LLM provider adapter."""

    def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        """Return the model's text response for one correction request."""

        ...


class LLMClientError(RuntimeError):
    """Safe, content-free error raised when an LLM provider call fails."""
