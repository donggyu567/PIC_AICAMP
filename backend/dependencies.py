"""Composition root for production and test dependencies."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock

from backend.config import Settings
from backend.services.correction_pipeline import CorrectionPipeline
from backend.storage.context_store import ContextResultStore
from models.llm_correction import (
    CorrectionEngine,
    CorrectionResultStore,
    LLMClient,
    OpenAIResponsesClient,
)


class LazyOpenAIClient:
    """Create the SDK adapter only when the first correction is requested."""

    def __init__(self) -> None:
        self._delegate: OpenAIResponsesClient | None = None
        self._lock = Lock()

    def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        delegate = self._delegate
        if delegate is None:
            with self._lock:
                if self._delegate is None:
                    self._delegate = OpenAIResponsesClient()
                delegate = self._delegate
        if delegate is None:
            raise RuntimeError("OpenAI client was not initialized")
        return delegate.complete(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )


@dataclass(frozen=True)
class Services:
    settings: Settings
    pipeline: CorrectionPipeline


def build_services(
    settings: Settings,
    *,
    llm_client: LLMClient | None = None,
) -> Services:
    client = llm_client if llm_client is not None else LazyOpenAIClient()
    pipeline = CorrectionPipeline(
        correction_engine=CorrectionEngine(client),
        correction_store=CorrectionResultStore(settings.corrections_root),
        context_store=ContextResultStore(settings.contexts_root),
        history_size=settings.history_size,
    )
    return Services(settings=settings, pipeline=pipeline)
