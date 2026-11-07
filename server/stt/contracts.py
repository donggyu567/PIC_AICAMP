"""앱 WebSocket 경계의 메시지 형식. 연결 순서는 중계 코드에서 관리한다."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from server.config import MAX_AUDIO_CHUNK_BYTES, MAX_SESSION_SECONDS


class Message(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class StartMessage(Message):
    type: Literal["start"]
    consent: Literal[True]
    audio_format: Literal["pcm_s16le"]
    sample_rate: Literal[16000]
    channels: Literal[1]


class StopMessage(Message):
    type: Literal["stop"]


client_message_adapter = TypeAdapter(
    Annotated[StartMessage | StopMessage, Field(discriminator="type")]
)


def parse_client_message(payload: str) -> StartMessage | StopMessage:
    return client_message_adapter.validate_json(payload)


def validate_audio_chunk(chunk: bytes) -> None:
    # 바이트 길이만 검증한다. 실제 인코딩은 앱이 계약대로 생성해야 한다.
    if not chunk or len(chunk) > MAX_AUDIO_CHUNK_BYTES or len(chunk) % 2:
        raise ValueError("PCM chunk must contain 1-16000 complete 16-bit samples")


class SessionMessage(Message):
    conversation_id: str = Field(min_length=1)


class ReadyMessage(SessionMessage):
    type: Literal["ready"] = "ready"
    max_session_seconds: int = MAX_SESSION_SECONDS


class StatusMessage(SessionMessage):
    type: Literal["status"] = "status"
    status: Literal["recognizing", "finalizing"]


class TranscriptMessage(SessionMessage):
    type: Literal["transcript"] = "transcript"
    utterance_id: int = Field(ge=1)
    text: str = Field(min_length=1, repr=False)


class StoppedMessage(SessionMessage):
    type: Literal["stopped"] = "stopped"
    reason: Literal["user_stop", "time_limit"]
    last_utterance_id: int = Field(ge=0)


class ErrorMessage(Message):
    type: Literal["error"] = "error"
    conversation_id: str | None = None
    code: Literal[
        "invalid_message", "invalid_audio", "invalid_state",
        "stt_unavailable", "stt_failed", "finalization_timeout",
    ]
    message: str  # 서버가 정한 안내 문구만 사용. 공급자 응답·원문은 넣지 않는다.
