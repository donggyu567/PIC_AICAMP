"""Orchestrate correction, context construction, and persistence."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Literal

from backend.errors import (
    ContextNotFoundError,
    ConversationConflictError,
    PersistenceError,
    RequestContractError,
    UpstreamCorrectionError,
)
from backend.storage.context_store import (
    ContextOutputConflictError,
    ContextOutputError,
    ContextResultStore,
    StoredConversationContext,
)
from models.context_manager import (
    ConversationContext,
    ConversationContextManager,
    Utterance,
    merge_utterance,
)
from models.context_manager.loader import InputDataError
from models.llm_correction import (
    ContractError,
    CorrectionEngine,
    CorrectionOutputConflictError,
    CorrectionOutputError,
    CorrectionResult,
    CorrectionResultStore,
    CorrectionValidationError,
    LLMClientError,
    LLMResponseError,
    MaskedTranscript,
    validate_correction_against_input,
)


@dataclass(frozen=True)
class ProcessedUtterance:
    status: Literal["created", "cached"]
    context: ConversationContext
    context_path: Path
    storage_key: str


class CorrectionPipeline:
    def __init__(
        self,
        *,
        correction_engine: CorrectionEngine,
        correction_store: CorrectionResultStore,
        context_store: ContextResultStore,
        history_size: int = 5,
    ) -> None:
        if not isinstance(correction_engine, CorrectionEngine):
            raise TypeError("correction_engine must be a CorrectionEngine")
        if not isinstance(correction_store, CorrectionResultStore):
            raise TypeError("correction_store must be a CorrectionResultStore")
        if not isinstance(context_store, ContextResultStore):
            raise TypeError("context_store must be a ContextResultStore")
        if (
            not isinstance(history_size, int)
            or isinstance(history_size, bool)
            or history_size < 0
        ):
            raise ValueError("history_size must be a non-negative integer")

        self._correction_engine = correction_engine
        self._correction_store = correction_store
        self._context_store = context_store
        self._history_size = history_size
        self._lock_guard = Lock()
        self._conversation_locks: dict[str, Lock] = {}

    def process(self, payload: Mapping[str, object]) -> ProcessedUtterance:
        try:
            transcript = MaskedTranscript.from_dict(payload)
        except (ContractError, TypeError):
            raise RequestContractError from None

        with self._conversation_lock(transcript.conversation_id):
            return self._process_locked(transcript)

    def get_latest(self, conversation_id: str) -> ProcessedUtterance:
        if (
            not isinstance(conversation_id, str)
            or not conversation_id.strip()
            or conversation_id != conversation_id.strip()
            or len(conversation_id) > 128
        ):
            raise RequestContractError

        with self._conversation_lock(conversation_id):
            try:
                stored = self._context_store.load_latest(conversation_id)
            except ContextOutputError:
                raise PersistenceError from None
            if stored is None:
                raise ContextNotFoundError
            return self._stored_result(stored, status="cached")

    def _process_locked(self, transcript: MaskedTranscript) -> ProcessedUtterance:
        try:
            existing = self._context_store.load(
                transcript.conversation_id,
                transcript.utterance_id,
            )
        except ContextOutputError:
            raise PersistenceError from None

        if existing is not None:
            self._ensure_same_request(existing.context.current, transcript)
            return self._stored_result(existing, status="cached")

        try:
            latest = self._context_store.load_latest(transcript.conversation_id)
        except ContextOutputError:
            raise PersistenceError from None
        self._require_next_utterance(transcript, latest)

        correction = self._load_or_create_correction(transcript)
        try:
            utterance = merge_utterance(
                transcript.to_dict(),
                correction.to_dict(),
            )
            context = self._build_context(latest, utterance)
        except (InputDataError, TypeError, ValueError):
            raise PersistenceError from None

        try:
            context_path = self._context_store.save(context)
        except ContextOutputConflictError:
            return self._resolve_context_publication_race(transcript)
        except ContextOutputError:
            raise PersistenceError from None

        return ProcessedUtterance(
            status="created",
            context=context,
            context_path=context_path,
            storage_key=self._context_store.relative_key(context_path),
        )

    def _load_or_create_correction(
        self,
        transcript: MaskedTranscript,
    ) -> CorrectionResult:
        try:
            correction = self._correction_store.load(transcript)
        except CorrectionOutputConflictError:
            raise ConversationConflictError from None
        except CorrectionOutputError:
            raise PersistenceError from None

        if correction is not None:
            self._validate_stored_correction(transcript, correction)
            return correction

        try:
            generated = self._correction_engine.correct(transcript)
        except (LLMClientError, LLMResponseError, CorrectionValidationError):
            raise UpstreamCorrectionError from None

        try:
            self._correction_store.save(generated)
            return generated
        except CorrectionOutputConflictError:
            try:
                winner = self._correction_store.load(transcript)
            except CorrectionOutputError:
                raise PersistenceError from None
            if winner is None:
                raise PersistenceError
            self._validate_stored_correction(transcript, winner)
            return winner
        except CorrectionOutputError:
            raise PersistenceError from None

    @staticmethod
    def _validate_stored_correction(
        transcript: MaskedTranscript,
        correction: CorrectionResult,
    ) -> None:
        try:
            validate_correction_against_input(transcript, correction)
        except ContractError:
            raise ConversationConflictError from None

    def _build_context(
        self,
        latest: StoredConversationContext | None,
        utterance: Utterance,
    ) -> ConversationContext:
        manager = ConversationContextManager(history_size=self._history_size)
        if latest is not None:
            for previous in [*latest.context.history, latest.context.current]:
                manager.add(previous)
        return manager.add(utterance)

    @staticmethod
    def _require_next_utterance(
        transcript: MaskedTranscript,
        latest: StoredConversationContext | None,
    ) -> None:
        expected_id = 1 if latest is None else latest.context.current.utterance_id + 1
        if transcript.utterance_id != expected_id:
            raise ConversationConflictError

    @staticmethod
    def _ensure_same_request(
        utterance: Utterance,
        transcript: MaskedTranscript,
    ) -> None:
        if (
            utterance.schema_version != transcript.schema_version
            or utterance.conversation_id != transcript.conversation_id
            or utterance.utterance_id != transcript.utterance_id
            or utterance.masked_text != transcript.masked_text
            or utterance.has_masked_data != transcript.has_masked_data
            or tuple(utterance.masked_types) != transcript.masked_types
        ):
            raise ConversationConflictError

    def _resolve_context_publication_race(
        self,
        transcript: MaskedTranscript,
    ) -> ProcessedUtterance:
        try:
            stored = self._context_store.load(
                transcript.conversation_id,
                transcript.utterance_id,
            )
        except ContextOutputError:
            raise PersistenceError from None
        if stored is None:
            raise PersistenceError
        self._ensure_same_request(stored.context.current, transcript)
        return self._stored_result(stored, status="cached")

    def _stored_result(
        self,
        stored: StoredConversationContext,
        *,
        status: Literal["cached"],
    ) -> ProcessedUtterance:
        return ProcessedUtterance(
            status=status,
            context=stored.context,
            context_path=stored.path,
            storage_key=self._context_store.relative_key(stored.path),
        )

    def _conversation_lock(self, conversation_id: str) -> Lock:
        with self._lock_guard:
            return self._conversation_locks.setdefault(conversation_id, Lock())
