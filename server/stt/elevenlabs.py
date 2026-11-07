"""ElevenLabs WebSocket 연결과 공급자 메시지 변환."""

import asyncio
import base64
import json
from contextlib import asynccontextmanager
from urllib.parse import urlencode

from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import WebSocketException

from server.config import PROVIDER_TIMEOUT_SECONDS, SAMPLE_RATE, SttSettings


class SttError(Exception):
    """앱에 공개 가능한 오류 코드만 보존한다."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


async def receive_event(connection: ClientConnection) -> dict:
    try:
        event = json.loads(await connection.recv())
    except (ValueError, WebSocketException, OSError):
        raise SttError("stt_failed") from None
    if not isinstance(event, dict):
        raise SttError("stt_failed")
    kind = event.get("message_type")
    if kind not in ("session_started", "partial_transcript", "committed_transcript"):
        # 공급자 오류 메시지에 입력 내용이 포함될 수 있어 그대로 전달하지 않는다.
        raise SttError("stt_failed")
    if kind != "session_started" and not isinstance(event.get("text"), str):
        raise SttError("stt_failed")
    return event


async def send_audio(connection: ClientConnection, chunk: bytes, *, commit: bool = False) -> None:
    payload = {
        "message_type": "input_audio_chunk",
        "audio_base_64": base64.b64encode(chunk).decode("ascii"),
        "sample_rate": SAMPLE_RATE,
        "commit": commit,
    }
    try:
        await asyncio.wait_for(connection.send(json.dumps(payload)), PROVIDER_TIMEOUT_SECONDS)
    except (TimeoutError, WebSocketException, OSError):
        raise SttError("stt_failed") from None


@asynccontextmanager
async def open_stt_connection(settings: SttSettings):
    query = urlencode({
        "model_id": settings.model_id,
        "audio_format": settings.audio_format,
        "language_code": settings.language_code,
        "commit_strategy": settings.commit_strategy,
    })
    connection = None
    # 음성을 보내기 전의 일시적 접속 실패만 한 번 재시도한다.
    for attempt in range(2):
        try:
            connection = await connect(
                f"{settings.url}?{query}",
                additional_headers={"xi-api-key": settings.api_key},
                open_timeout=PROVIDER_TIMEOUT_SECONDS,
                close_timeout=2, max_size=256_000, max_queue=8,
            )
            break
        except (OSError, TimeoutError):
            if attempt == 1:
                raise SttError("stt_unavailable") from None
        except WebSocketException:
            raise SttError("stt_unavailable") from None
    try:
        try:
            event = await asyncio.wait_for(receive_event(connection), PROVIDER_TIMEOUT_SECONDS)
            if event["message_type"] != "session_started":
                raise SttError("stt_unavailable")
        except (TimeoutError, SttError):
            raise SttError("stt_unavailable") from None
        yield connection
    finally:
        await connection.close()
